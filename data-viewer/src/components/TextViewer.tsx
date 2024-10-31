"use client";
import { useEffect, useState } from "react";
import {FileQueryUrl} from "@/components/utils/FileQueryUrl";
import {ErrorBoundary} from "react-error-boundary";
import {CircularProgress} from "@mui/material";
import {Stack} from "@mui/system";
import {Fallback} from "@/components/utils/FallbackPage";

export default function TextViewer(
    filename: string,
    apiUrl: string,
    instrument?: string,
    experimentNumber?: string,
    userNumber?: string,
) {
    // We need to turn the env var into a full url as the h5provider can not take just the route.
    // Typically, we expect API_URL env var to be /plottingapi in staging and production
    const [text, setText] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(true);

    useEffect(() => {
        setLoading(true)
        const loadedToken = localStorage.getItem("scigateway:token") ?? ""
        const fileQueryUrl = FileQueryUrl(apiUrl, instrument, experimentNumber, userNumber);
        if (fileQueryUrl == null) {
            throw new Error("")
        }

        const fileQueryParams = `filename=${filename}`;
        const headers: { [key: string]: string } = {'Content-Type': 'application/json'};
        if (loadedToken != "") {
            headers['Authorization'] = `Bearer ${loadedToken}`;
        }

        fetch(`${fileQueryUrl}?${fileQueryParams}`, {method: 'GET', headers})
            .then((res) => {
                if (!res.ok) {
                    throw new Error(res.statusText);
                }
                return res.text();
            })
            .then((data) => {
                const filepath_to_use = data.split("%20").join(" ").replace(/"/g, "")
                setText(filepath_to_use);
                setLoading(false)
            })
    }, [apiUrl, instrument, experimentNumber, userNumber, filename])

  return (
      <ErrorBoundary FallbackComponent={Fallback}>
          {loading ? (
              <Stack spacing={2} sx={{justifyContent: 'center', alignItems: 'center', height: '100%', width: '100%'}}>
                  <p>Finding your file</p>
                  <CircularProgress/>
              </Stack>
          ) : (
              <div>
                  <pre>{text}</pre>
              </div>
          )}
      </ErrorBoundary>
  );
};
