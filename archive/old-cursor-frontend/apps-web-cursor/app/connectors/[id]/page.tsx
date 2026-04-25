import { redirect } from "next/navigation";

export default function ConnectorDetailRedirectPage({ params }: { params: { id: string } }) {
  redirect(`/integrations/${params.id}`);
}
