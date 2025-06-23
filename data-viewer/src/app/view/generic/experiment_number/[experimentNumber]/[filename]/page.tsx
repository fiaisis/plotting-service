import NexusViewer from "@/components/NexusViewer";
import "../../../../../globals.css";
import TextViewer from "@/components/TextViewer";

export default async function GenericExperimentDataPage({
  params,
}: {
  params: Promise<{ experimentNumber: string; filename: string }>;
}) {
  // We expect a route of /generic/experiment_number/filename
  // This will result in a slug list of [experiment_number, filename]
  const { experimentNumber, filename } = await params;
  const fileExtension = filename.split(".").pop();
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";

  return (
    <main className="h5-container">
      {fileExtension === "txt" ? (
        <TextViewer
          apiUrl={apiUrl}
          experimentNumber={experimentNumber}
          filename={filename}
        />
      ) : (
        <NexusViewer
          apiUrl={apiUrl}
          experimentNumber={experimentNumber}
          filename={filename}
        />
      )}
    </main>
  );
}
