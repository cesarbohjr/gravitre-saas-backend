import { render, screen } from "@testing-library/react"
import { OutboundProviderCards } from "../outbound-provider-cards"

describe("Outbound provider cards", () => {
  it("shows providers without claiming they are connected", () => {
    render(<OutboundProviderCards />)
    for (const name of ["Smartlead", "Instantly", "QuickMail", "Hunter", "Snov.io"]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument()
    }
    expect(screen.getByText("Sending gated")).toBeInTheDocument()
    expect(screen.getAllByText("Nango setup pending")).toHaveLength(4)
    expect(screen.queryByText("Connected")).not.toBeInTheDocument()
  })
})
