/**
 * wizardcheck — x402 service handler.
 */
export default async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);
  // const myParam = url.searchParams.get("myParam") ?? "default";

  return Response.json({
    message: "Hello from wizardcheck!",
    timestamp: new Date().toISOString(),
  });
}
