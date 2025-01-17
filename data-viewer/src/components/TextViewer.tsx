"use client";
import { useEffect, useState } from "react";
import {FileQueryUrl} from "@/components/utils/FileQueryUrl";
import {ErrorBoundary} from "react-error-boundary";
import {CircularProgress} from "@mui/material";
import {Stack} from "@mui/system";
import {Fallback} from "@/components/utils/FallbackPage";
import {App} from "@h5web/app";

export default function TextViewer(props: {
    filename: string;
    apiUrl: string;
    instrument?: string;
    experimentNumber?: string;
    userNumber?: string;
}) {
    // We need to turn the env var into a full url as the h5provider can not take just the route.
    // Typically, we expect API_URL env var to be /plottingapi in staging and production
    const [text, setText] = useState<string>("");
    const [loading, setLoading] = useState<boolean>(true);

    useEffect(() => {
        setLoading(true)
        const loadedToken = localStorage.getItem("scigateway:token") ?? ""
        const textQueryUrl = `${props.apiUrl}/text/instrument/${props.instrument}/experiment_number/${props.experimentNumber}`;
        const textQueryParams = `filename=${props.filename}`;
        const headers: { [key: string]: string } = {'Content-Type': 'application/json'};
        if (loadedToken != "") {
            headers['Authorization'] = `Bearer ${loadedToken}`;
        }

        fetch(`${textQueryUrl}?${textQueryParams}`, {method: 'GET', headers})
            .then((res) => {
                if (!res.ok) {
                    throw new Error(res.statusText);
                }
                return res.text();
            })
            .then((resultText) => {
                setText(resultText)
                setLoading(false)
            }).finally(() => {
                if (loading) {
                    setLoading(false)
                    throw new Error("Data could not be loaded");
                }
            })
    }, [props.apiUrl, props.instrument, props.experimentNumber, props.filename])

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
                  <App propagateErrors/>
              </div>
          )}
      </ErrorBoundary>
  );
};
