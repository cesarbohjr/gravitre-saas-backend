import json
import socket
from unittest.mock import Mock

import pytest

from app.services.native_runtime import gateway


@pytest.mark.parametrize('stage', ['dns', 'socket'])
def test_connect_failure_reports_fixed_stage_without_destination_or_error_text(monkeypatch, capsys, stage):
    handler=object.__new__(gateway.Handler)
    handler.path='private-page.example:443'
    handler.send_error=Mock()
    monkeypatch.setattr(gateway,'CONFIG',{'allowed_hosts':['private-page.example']})
    monkeypatch.setattr(gateway,'control',Mock(return_value={}))
    monkeypatch.setattr(gateway,'public_addresses',Mock(return_value=['93.184.216.34']))
    failure=socket.gaierror('PRIVATE-EXCEPTION-PAYLOAD')
    if stage=='dns':gateway.public_addresses.side_effect=failure
    else:monkeypatch.setattr(gateway.socket,'create_connection',Mock(side_effect=failure))
    handler.do_CONNECT()
    output=capsys.readouterr().err
    assert json.loads(output)=={'gateway_failure_stage':'connect_'+stage,'gateway_failure_class':'gaierror','known_parameter_flags':[]}
    assert 'PRIVATE-EXCEPTION-PAYLOAD' not in output and 'private-page.example' not in output
    handler.send_error.assert_called_once_with(403,'Native destination blocked')
