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
  filepath: string;
  apiUrl: string;
}) {
  // We need to turn the env var into a full url as the h5provider can not take just the route.
  // Typically, we expect API_URL env var to be /plottingapi in staging and production
  const [hostName, setHostName] = useState<string>("");
  const [protocol, setProtocol] = useState<string>("http");
  useEffect(() => {
    setHostName(window.location.hostname);
    setProtocol(window.location.protocol);
  }, []);
  const token = localStorage.getItem("scigateway:token");
  const apiUrl =
    props.apiUrl === "http://localhost:8000"
      ? props.apiUrl
      : `${protocol}//${hostName}/plottingapi`;

  return (
    <ErrorBoundary FallbackComponent={Fallback}>
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
        <App propagateErrors />
      </H5GroveProvider>
    </ErrorBoundary>
  );
}
