"use client";
import "@h5web/app/dist/styles.css";
import {App, H5GroveProvider} from "@h5web/app";
import {useEffect, useMemo, useState} from "react";

export default function NexusViewer(props: {
  filepath: string;
  apiUrl: string;
}) {

    const [hostName, setHostName] = useState<string>("")
    const [protocol, setProtocol] = useState<string>("http")
    useEffect(() => {
        setHostName(window.location.hostname)
        setProtocol(window.location.protocol)
    }, [])

    const apiUrl = props.apiUrl === "http://localhost:8000" ? props.apiUrl : `${protocol}//${hostName}/plottingapi`

    return (
    <H5GroveProvider
      url={apiUrl}
      filepath={props.filepath}
      axiosConfig={useMemo(
        () => ({
          params: { file: props.filepath },
        }),
        [props.filepath],
      )}
    >
      <App />
    </H5GroveProvider>
  );
}
