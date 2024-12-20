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
    const {instrument, experimentNumber, filename} = params;
    const fileExtension = filename.split(".").pop();
    const apiUrl = process.env.API_URL ?? "http://localhost:8000";
    // temporary check to force a value onto fiaApiUrl
    const fiaApiUrl = (process.env.FIA_API_URL || process.env.NEXT_PUBLIC_FIA_API_URL) || "http://localhost:8001";

    console.log("non generic env vars \n")
    
    console.log("\n fiaApiUrl: ", fiaApiUrl, "\n NEXT_PUBLIC_FIA_API_URL: ", process.env.NEXT_PUBLIC_FIA_API_URL, "\n normal FAPI_URL: ", process.env.FIA_API_URL)

    console.log("\n\n process.env.REACT_APP fiaApiUrl is ", process.env.REACT_APP_FIA_API_URL)

    console.log("Checking to see if any apiUrl is defined (before adding it to test worflow")
    console.log("\n apiUrl: ", apiUrl, "\n NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL, "\n normal ", process.env.API_URL)

    return (
        <main className="h5-container">
            {fileExtension === "txt" ? (
                <TextViewer
                    apiUrl={apiUrl}
                    fiaApiUrl={fiaApiUrl}
                    experimentNumber={experimentNumber}
                    instrument={instrument}
                    filename={filename}
                />
            ) : (
                <NexusViewer
                    apiUrl={apiUrl}
                    fiaApiUrl={fiaApiUrl}
                    experimentNumber={experimentNumber}
                    instrument={instrument}
                    filename={filename}
                />
            )}
        </main>
    );
};
