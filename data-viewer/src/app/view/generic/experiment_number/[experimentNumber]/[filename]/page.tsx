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
    const {experimentNumber, filename} = params;
    const fileExtension = filename.split(".").pop();
    const apiUrl = process.env.API_URL ?? "http://localhost:8000";
    const fiaApiUrl = process.env.FIA_API_URL ?? "http://localhost:8001";
    
    return (
        <main className="h5-container">
            {fileExtension === "txt" ? (
                <TextViewer
                    apiUrl={apiUrl}
                    fiaApiUrl={fiaApiUrl}
                    experimentNumber={experimentNumber}
                    filename={filename}
                />
            ) : (
                <NexusViewer
                    apiUrl={apiUrl}
                    fiaApiUrl={fiaApiUrl}
                    experimentNumber={experimentNumber}
                    filename={filename}
                />
            )}
        </main>
    );
};
