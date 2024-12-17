"use client";
import "@h5web/app/dist/styles.css";
import {App, H5GroveProvider} from "@h5web/app";
import {useEffect, useState} from "react";
import {ErrorBoundary} from "react-error-boundary";
import {CircularProgress, Stack} from '@mui/material';
import {FileQueryUrl} from "@/components/utils/FileQueryUrl";
import {Fallback} from "@/components/utils/FallbackPage";

export default function NexusViewer(props :{
    filename: string;
    apiUrl: string;
    fiaApiUrl: string
    instrument?: string;
    experimentNumber?: string;
    userNumber?: string;
}
) {
    // We need to turn the env var into a full url as the h5provider can not take just the route.
    // Typically, we expect API_URL env var to be /plottingapi in staging and production
    const [filepath, setFilePath] = useState<string>("");
    const [token, setToken] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(true);
    const [groveApiUrl, setApiUrl] = useState<string>(props.apiUrl)

    console.log("Duplicated to see what the values would have been within the useeffect, Nexus viewer, starting FileQueryURL with: ", props.fiaApiUrl, "", props.instrument, "", props.experimentNumber, "", props.userNumber)
    const fileQueryUrl = FileQueryUrl(props.fiaApiUrl, props.instrument, props.experimentNumber, props.userNumber);

    console.log("returned file query url ", fileQueryUrl)
    const loadedToken = localStorage.getItem("scigateway:token") ?? ""
    console.log("is this a loaded token", loadedToken, " the token")

    const fileQueryParams = `filename=${props.filename}`;
    const headers: { [key: string]: string } = {'Content-Type': 'application/json'};
    if (loadedToken != "") {
        headers['Authorization'] = `Bearer ${loadedToken}`;
    }

    fetch(`${fileQueryUrl}?${fileQueryParams}`, {method: 'GET', headers})
    .then((res) => {
        console.log("result of get ", res)
        if (!res.ok) {
            throw new Error(res.statusText);
        }
        return res.text();
    })
    .then((data) => {
        const filepath_to_use = data.split("%20").join(" ").replace(/"/g, "")
        setFilePath(filepath_to_use);
        setLoading(false)
    })

    useEffect(() => {
        setLoading(true)
        const loadedToken = localStorage.getItem("scigateway:token") ?? ""
        setToken(loadedToken);
        setApiUrl(props.apiUrl.includes("localhost") ? props.apiUrl : `${window.location.protocol}//${window.location.hostname}/plottingapi`)

        const fileQueryUrl = FileQueryUrl(props.fiaApiUrl, props.instrument, props.experimentNumber, props.userNumber);
        if (fileQueryUrl == null) {
            throw new Error("The API file query URL was not rendered correctly and returned null")
        }

        const fileQueryParams = `filename=${props.filename}`;
        const headers: { [key: string]: string } = {'Content-Type': 'application/json'};
        if (loadedToken != "") {
            headers['Authorization'] = `Bearer ${loadedToken}`;
        }

        fetch(`${fileQueryUrl}?${fileQueryParams}`, {method: 'GET', headers})
            .then((res) => {
                console.log("result of get ", res)
                if (!res.ok) {
                    throw new Error(res.statusText);
                }
                return res.text();
            })
            .then((data) => {
                const filepath_to_use = data.split("%20").join(" ").replace(/"/g, "")
                setFilePath(filepath_to_use);
                setLoading(false)
            })
    }, [props.apiUrl, props.instrument, props.experimentNumber, props.userNumber, props.filename, props.fiaApiUrl])

    return (
        <ErrorBoundary FallbackComponent={Fallback}>
            {loading ? (
                <Stack spacing={2} sx={{justifyContent: 'center', alignItems: 'center', height: '100%', width: '100%'}}>
                    <p>Finding your file</p>
                    <CircularProgress/>
                </Stack>
            ) : (
                <H5GroveProvider
                    url={groveApiUrl}
                    filepath={filepath}
                    axiosConfig={{
                        params: {file: filepath},
                        headers: {
                            Authorization: `Bearer ${token}`,
                        }
                    }}
                >
                    <App propagateErrors/>
                </H5GroveProvider>)}
        </ErrorBoundary>
    );
}
