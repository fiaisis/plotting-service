import NexusViewer from "@/components/NexusViewer";
import "../../../../../globals.css";
import TextViewer from "@/components/TextViewer";

export default function GenericUserDataPage({
  params,
}: {
  params: { userNumber: string; filename: string };
}) {
  // We expect a route of /generic/user_number/filename
  // This will result in a slug list of [user_number, filename]
  const { userNumber, filename } = params;
  const fileExtension = filename.split(".").pop() ?? "nxs";
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const textFiles: Array<string> = ["txt", "csv", "gss", "abc"];
  return (
    <main className="h5-container">
      {textFiles.includes(fileExtension) ? (
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
