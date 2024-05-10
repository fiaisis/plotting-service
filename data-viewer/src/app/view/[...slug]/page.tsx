import {notFound} from "next/navigation";
import NexusViewer from "@/components/NexusViewer";
import "../../globals.css";

export default function DataPage({ params }: { params: { slug: string[] } }) {
  // We expect a route of /instrument_name/experiment_number/filename
  // This will result in a slug list of [instrument_name, experiment_number, filename]
  const [instrument, experimentNumber, filename] = params.slug;
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  if (params.slug.length != 3) {
    notFound();
  }
  return (
    <main className="h5-container">
      <NexusViewer
        filepath={`${instrument.toUpperCase()}/RBNumber/RB${experimentNumber}/autoreduced/${filename}`}
        apiUrl={apiUrl}
      />
    </main>
  );
}
