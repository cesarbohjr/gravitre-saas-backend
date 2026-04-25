import { toast as sonnerToast } from "sonner"

// Gravitre-specific toast variants
export const toast = {
  // Success toast with green styling
  success: (message: string, options?: { description?: string }) => {
    sonnerToast.success(message, {
      description: options?.description,
    })
  },

  // Error toast with red styling
  error: (message: string, options?: { description?: string }) => {
    sonnerToast.error(message, {
      description: options?.description,
    })
  },

  // Warning toast with amber styling
  warning: (message: string, options?: { description?: string }) => {
    sonnerToast.warning(message, {
      description: options?.description,
    })
  },

  // Info toast with blue styling
  info: (message: string, options?: { description?: string }) => {
    sonnerToast.info(message, {
      description: options?.description,
    })
  },

  // Loading toast with spinner
  loading: (message: string, options?: { description?: string }) => {
    return sonnerToast.loading(message, {
      description: options?.description,
    })
  },

  // Promise toast that shows loading, success, or error based on promise result
  promise: <T,>(
    promise: Promise<T>,
    options: {
      loading: string
      success: string | ((data: T) => string)
      error: string | ((error: unknown) => string)
    }
  ) => {
    return sonnerToast.promise(promise, options)
  },

  // Task completion toast
  taskComplete: (taskName: string, deliverableId?: string) => {
    sonnerToast.success("Task completed", {
      description: taskName,
      action: deliverableId
        ? {
            label: "View",
            onClick: () => {
              window.location.href = `/lite/deliverables?id=${deliverableId}`
            },
          }
        : undefined,
    })
  },

  // Deliverable ready toast
  deliverableReady: (title: string, deliverableId: string) => {
    sonnerToast.success("Deliverable ready", {
      description: title,
      action: {
        label: "Review",
        onClick: () => {
          window.location.href = `/lite/deliverables?id=${deliverableId}`
        },
      },
    })
  },

  // Approval required toast
  approvalRequired: (workflowName: string, approvalId: string) => {
    sonnerToast.warning("Approval required", {
      description: workflowName,
      action: {
        label: "Review",
        onClick: () => {
          window.location.href = `/approvals?id=${approvalId}`
        },
      },
    })
  },

  // External action toast (Slack, HubSpot, etc.)
  externalAction: (platform: string, action: string) => {
    sonnerToast.success(`${platform}`, {
      description: action,
    })
  },

  // Workflow started toast
  workflowStarted: (workflowName: string) => {
    sonnerToast.info("Workflow started", {
      description: workflowName,
    })
  },

  // Agent assigned toast
  agentAssigned: (agentName: string, taskName: string) => {
    sonnerToast.info(`${agentName} assigned`, {
      description: taskName,
    })
  },

  // Dismiss a specific toast
  dismiss: (toastId?: string | number) => {
    sonnerToast.dismiss(toastId)
  },
}

// Re-export for direct use
export { sonnerToast }
