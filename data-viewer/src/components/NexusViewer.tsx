"use client";
import "@h5web/app/dist/styles.css";
import { App, H5GroveProvider } from "@h5web/app";
import { useEffect, useMemo, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";

const Fallback = () => (
  <div
    style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      flexDirection: "column",
      height: "100vh",
    }}
  >
    <img src={"/monkey.webp"} alt={"Monkey holding excellent website award"} />
    <h1>Something Went Wrong</h1>
    <p>
      Return <a href={"https://reduce.isis.cclrc.ac.uk"}>Home</a>
    </p>
    <p>
      If this keeps happening email{" "}
      <a href={"mailto:fia@stfc.ac.uk"}>fia-support</a>.
    </p>
  </div>
);

export default function NexusViewer(props: {
  filename: string;
  instrument: string;
  experimentNumber: string;
  apiUrl: string;
}) {
  // We need to turn the env var into a full url as the h5provider can not take just the route.
  // Typically, we expect API_URL env var to be /plottingapi in staging and production
  const [hostName, setHostName] = useState<string>("");
  const [protocol, setProtocol] = useState<string>("http");
  const [filepath, setFilePath] = useState<string>("");
  useEffect(() => {
    setHostName(window.location.hostname);
    setProtocol(window.location.protocol);
  }, []);
  const token = localStorage.getItem("scigateway:token") ?? "";
  const groveApiUrl =
    props.apiUrl === "http://localhost:8000"
      ? props.apiUrl
      : `${protocol}//${hostName}/plottingapi`;
  const fileQueryUrl = `${props.apiUrl}/find_file/instrument/${props.instrument}/experiment_number/${props.experimentNumber}`
  const fileQueryParams = `filename=${props.filename}`;

  useEffect(() => {
    const headers: { [key: string]: string } = {'Content-Type': 'application/json'};
    if (token != "") {
      headers['Authorization'] = `Bearer ${token}`;
    }
    fetch(`${fileQueryUrl}?${fileQueryParams}`, {method: 'GET', headers})
      .then((res) => {
            if (!res.ok) {
              throw new Error(res.statusText);
            }
            return res.text();
      })
      .then((data) => {
        setFilePath(data);
      })
  }, [])
  return (
    <ErrorBoundary FallbackComponent={Fallback}>
      <H5GroveProvider
        url={groveApiUrl}
        filepath={filepath.split("%20").join(" ")}
        axiosConfig={useMemo(
          () => ({
            params: { file: filepath.split("%20").join(" ").replace(/"/g, "") },
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }),
          [filepath],
        )}
      >
        <App propagateErrors />
      </H5GroveProvider>
    </ErrorBoundary>
  );
}
