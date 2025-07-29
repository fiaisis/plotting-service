import NexusViewer from "@/components/NexusViewer";
import "../../../../../globals.css";
import TextViewer from "@/components/TextViewer";

export default function GenericExperimentDataPage({
  params,
}: {
  params: { experimentNumber: string; filename: string };
}) {
  // We expect a route of /generic/experiment_number/filename
  // This will result in a slug list of [experiment_number, filename]
  const { experimentNumber, filename } = params;
  const fileExtension = filename.split(".").pop() ?? "nxs";
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const textFiles: Array<string> = ["txt", "csv", "gss", "abc"];
  return (
    <main className="h5-container">
      {textFiles.includes(fileExtension) ? (
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
