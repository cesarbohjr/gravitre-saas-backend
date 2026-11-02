"""Run real DeepEval exact-tool scoring, without inference or network access.

This is a narrow SDK experiment against a strict trace reference. It is not the
existing conversational judge baseline, an independently reviewed quality study,
or permission to install DeepEval in the application.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stdout
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
from statistics import median
import sys
import time
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def run():
    os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
    os.environ['DEEPEVAL_FILE_SYSTEM'] = 'READ_ONLY'
    os.environ['OTEL_SDK_DISABLED'] = 'true'
    os.environ['DEEPEVAL_EVAL_MODE'] = 'llm'
    for name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'CONFIDENT_API_KEY'):
        os.environ.pop(name, None)
    attempts = []

    def forbidden(*_, **__):
        attempts.append(True)
        raise RuntimeError('Network forbidden in isolated evaluator experiment')

    original_connect = socket.socket.connect

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            return forbidden()
        return original_connect(sock, address)

    raw = (HERE / 'tool_cases.json').read_bytes()
    corpus = json.loads(raw)
    assert corpus['independent_human_review'] is False
    assert len({row['id'] for row in corpus['cases']}) == len(corpus['cases'])
    rows = []
    with ExitStack() as stack:
        for target, replacement in (('socket.getaddrinfo', forbidden),
                                    ('socket.create_connection', forbidden),
                                    ('socket.socket.connect', connect),
                                    ('socket.socket.connect_ex', forbidden)):
            stack.enter_context(patch(target, replacement))
        import grpc
        import grpc.aio
        for module in (grpc, grpc.aio):
            for name in ('secure_channel', 'insecure_channel'):
                stack.enter_context(patch.object(module, name, forbidden))
        from deepeval.models import DeepEvalBaseLLM
        from deepeval.metrics import ToolCorrectnessMetric
        from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams
        import inspect
        assert importlib.metadata.version('deepeval') == '4.3.2'
        metric_hash = hashlib.sha256(Path(inspect.getfile(ToolCorrectnessMetric)).read_bytes()).hexdigest()

        class NoInference(DeepEvalBaseLLM):
            calls = 0

            def load_model(self):
                return None

            def get_model_name(self):
                return 'forbidden-inference'

            def generate(self, *_, **__):
                type(self).calls += 1
                raise RuntimeError('Inference forbidden in exact-tool experiment')

            async def a_generate(self, *_, **__):
                return self.generate()

        for case in corpus['cases']:
            start = time.perf_counter()
            reference = case['actual'] == case['expected']
            reference_ms = (time.perf_counter() - start) * 1000
            assert reference is case['label']
            metric = ToolCorrectnessMetric(model=NoInference(), eval_mode='llm',
                async_mode=False, strict_mode=True, should_exact_match=True,
                should_consider_ordering=True, evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
                include_reason=False)
            test_case = LLMTestCase(input='Fixed synthetic tool trace', actual_output='Synthetic result',
                tools_called=[ToolCall(**tool) for tool in case['actual']],
                expected_tools=[ToolCall(**tool) for tool in case['expected']])
            start = time.perf_counter()
            score = metric.measure(test_case, _show_indicator=False)
            elapsed = (time.perf_counter() - start) * 1000
            assert type(score) in (int, float) and score in (0, 1)
            rows.append({'case_id': case['id'], 'reference_pass': reference,
                'deepeval_pass': score == 1, 'label_pass': case['label'],
                'agreement': (score == 1) is case['label'],
                'reference_ms': reference_ms, 'deepeval_ms': elapsed})
        assert NoInference.calls == 0 and not attempts
    return {'schema_version': 1, 'scope': corpus['scope'], 'deepeval_version': importlib.metadata.version('deepeval'),
        'sdk_metric_sha256': metric_hash,
        'dataset_sha256': hashlib.sha256(raw).hexdigest(),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'lock_sha256': hashlib.sha256((HERE / 'requirements-deepeval.lock').read_bytes()).hexdigest(),
        'rows': rows, 'all_labels_detected': all(row['agreement'] for row in rows),
        'summary': {'count': len(rows), 'reference_accuracy': sum(row['reference_pass'] is row['label_pass'] for row in rows) / len(rows),
                    'deepeval_accuracy': sum(row['agreement'] for row in rows) / len(rows),
                    'reference_p50_ms': median(row['reference_ms'] for row in rows),
                    'deepeval_p50_ms': median(row['deepeval_ms'] for row in rows)},
        'inference_calls': 0, 'network_attempts': 0,
        'reference_kind': 'strict_exact_trace_reference_not_conversational_judge',
        'independent_human_review': False,
        'conversational_judgment_validity': 'NOT_RUN',
        'existing_fixed_baseline_quality_comparison': 'NOT_RUN',
        'framework_selection': 'BLOCKED_PENDING_FULL_COMPARISON',
        'production_certified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    with redirect_stdout(sys.stderr):
        report = run()
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'cases': len(report['rows']), 'all_labels_detected': report['all_labels_detected'],
                      'framework_selection': report['framework_selection']}))
    return 0 if report['all_labels_detected'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
