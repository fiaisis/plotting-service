import { notFound } from "next/navigation";
import NexusViewer from "@/components/NexusViewer";
import "../../../../globals.css";
import TextViewer from "@/components/TextViewer";

export default function DataPage({
  params,
}: {
  params: { instrument: string; experimentNumber: string; filename: string };
}) {
  // We expect a route of /instrument_name/experiment_number/filename
  // This will result in a slug list of [instrument_name, experiment_number, filename]
  const { instrument, experimentNumber, filename } = params;
  const fileExtension = filename.split(".").pop();
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";

  return (
    <main className="h5-container">
      {fileExtension === "txt" ? (
        <TextViewer
          apiUrl={apiUrl}
          experimentNumber={experimentNumber}
          instrument={instrument}
          filename={filename}
        />
      ) : (
        <NexusViewer
          filepath={`${instrument.toUpperCase()}/RBNumber/RB${experimentNumber}/autoreduced/${filename}`}
          apiUrl={apiUrl}
        />
      )}
    </main>
  );
}
