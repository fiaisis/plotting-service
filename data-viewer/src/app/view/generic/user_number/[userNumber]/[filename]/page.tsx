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
    const {userNumber, filename} = params;
    const fileExtension = filename.split(".").pop();
    const apiUrl = process.env.API_URL ?? "http://localhost:8000";
    const fiaApiUrl = process.env.FIA_API_URL ?? "http://localhost:8001";
    
    return (
        <main className="h5-container">
            {fileExtension === "txt" ? (
                <TextViewer
                    apiUrl={apiUrl}
                    fiaApiUrl={fiaApiUrl}
                    userNumber={userNumber}
                    filename={filename}
                />
            ) : (
                <NexusViewer
                    apiUrl={apiUrl}
                    fiaApiUrl={fiaApiUrl}
                    userNumber={userNumber}
                    filename={filename}
                />
            )}
        </main>
    );
};
