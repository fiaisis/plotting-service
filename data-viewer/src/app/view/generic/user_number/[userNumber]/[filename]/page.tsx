import NexusViewer from "@/components/NexusViewer";
import "../../../../../globals.css";
import TextViewer from "@/components/TextViewer";

export default async function GenericUserDataPage({
  params,
}: {
  params: Promise<{ userNumber: string; filename: string }>;
}) {
  // We expect a route of /generic/user_number/filename
  // This will result in a slug list of [user_number, filename]
  const { userNumber, filename } = await params;
  const fileExtension = filename.split(".").pop();
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";

  return (
    <main className="h5-container">
      {fileExtension === "txt" ? (
        <TextViewer
          apiUrl={apiUrl}
          userNumber={userNumber}
          filename={filename}
        />
      ) : (
        <NexusViewer
          apiUrl={apiUrl}
          userNumber={userNumber}
          filename={filename}
        />
      )}
    </main>
  );
}
