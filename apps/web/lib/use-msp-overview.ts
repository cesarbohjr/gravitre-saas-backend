"use client"

import useSWR from "swr"
import { mspProgramApi, type MspOverview } from "@/lib/msp-program"

export const MSP_OVERVIEW_KEY = "msp:program:overview"

/** Partner-program status of the current workspace (MSP, client, or neither). */
export function useMspOverview(enabled = true) {
  return useSWR<MspOverview>(enabled ? MSP_OVERVIEW_KEY : null, () => mspProgramApi.overview(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
}
