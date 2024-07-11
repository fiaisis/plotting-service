"use client";
import "@h5web/app/dist/styles.css";
import { App, H5GroveProvider } from "@h5web/app";
import { useEffect, useMemo, useState } from "react";

export default function NexusViewer(props: {
  filepath: string;
  apiUrl: string;
}) {
  // We need to turn the env var into a full url as the h5provider can not take just the route.
  // Typically, we expect API_URL env var to be /plottingapi in staging and production
  const [hostName, setHostName] = useState<string>("");
  const [protocol, setProtocol] = useState<string>("http");
  const [token, setToken] = useState<string>("");
  useEffect(() => {
    setHostName(window.location.hostname);
    setProtocol(window.location.protocol);
    setToken(localStorage.getItem("scigateway:token") ?? "");
  }, []);
  const apiUrl =
    props.apiUrl === "http://localhost:8000"
      ? props.apiUrl
      : `${protocol}//${hostName}/plottingapi`;

  return (
    <H5GroveProvider
      url={apiUrl}
      filepath={props.filepath.split("%20").join(" ")}
      axiosConfig={useMemo(
        () => ({
          params: { file: props.filepath.split("%20").join(" ") },
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }),
        [props.filepath],
      )}
    >
      <App />
    </H5GroveProvider>
  );
}
