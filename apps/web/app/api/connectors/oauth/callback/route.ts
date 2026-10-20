/** Fixed OAuth relay. Provider registrations and the managed environment must
 * select this callback together; deploying it alone does not change live grants.
 */
export const dynamic = "force-dynamic"

export function GET(request: Request) {
  const target = new URL("https://api.nango.dev/oauth/callback")
  target.search = new URL(request.url).search
  return new Response(null, { status: 308, headers: {
    Location: target.toString(),
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
  } })
}
