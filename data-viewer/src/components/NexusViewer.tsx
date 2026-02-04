"use client";
import "@h5web/app/dist/styles.css";
import { App, H5GroveProvider, createBasicFetcher } from "@h5web/app";
import { useEffect, useMemo, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { CircularProgress, Stack } from "@mui/material";
import { FileQueryUrl } from "@/components/utils/FileQueryUrl";
import { Fallback } from "@/components/utils/FallbackPage";

// Clear old h5web storage entries once (result of 15.0.0 migration)
function clearOldH5webStorage() {
  try {
    if (typeof window === "undefined") {
      return;
    }
    const clearedVersion = window.localStorage.getItem(
      "data-viewer:h5web-storage-cleared",
    );
    if (clearedVersion === "15") {
      return;
    }

    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith("h5web:")) {
        window.localStorage.removeItem(key);
      }
    }

    window.localStorage.setItem("data-viewer:h5web-storage-cleared", "15");
  } catch {}
}

clearOldH5webStorage();

export default function NexusViewer(props: {
  filename: string;
  apiUrl: string;
  instrument?: string;
  experimentNumber?: string;
  userNumber?: string;
}) {
  // We need to turn the env var into a full url as the h5provider can not take just the route.
  // Typically, we expect API_URL env var to be /plottingapi in staging and production
  const [filepath, setFilePath] = useState<string>("");
  const [token, setToken] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [groveApiUrl, setApiUrl] = useState<string>(props.apiUrl);

  const fetcher = useMemo(() => {
    const headers: HeadersInit = {};
    if (token !== "") {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return createBasicFetcher({ headers });
  }, [token]);

  useEffect(() => {
    setLoading(true);
    const loadedToken = localStorage.getItem("scigateway:token") ?? "";
    setToken(loadedToken);
    setApiUrl(
      props.apiUrl.includes("localhost")
        ? props.apiUrl
        : `${window.location.protocol}//${window.location.hostname}/plottingapi`,
    );

    const fileQueryUrl = FileQueryUrl(
      props.apiUrl,
      props.instrument,
      props.experimentNumber,
      props.userNumber,
    );
    if (fileQueryUrl == null) {
      throw new Error(
        "The API file query URL was not rendered correctly and returned null",
      );
    }

    const fileQueryParams = `filename=${props.filename}`;
    const headers: { [key: string]: string } = {
      "Content-Type": "application/json",
    };
    if (loadedToken != "") {
      headers["Authorization"] = `Bearer ${loadedToken}`;
    }

    fetch(`${fileQueryUrl}?${fileQueryParams}`, { method: "GET", headers })
      .then((res) => res.text())
      .then((data) => {
        const filepath_to_use = data
          .split("%20")
          .join(" ")
          .split("%C")
          .join(",")
          .replace(/"/g, "");
        setFilePath(filepath_to_use);
      })
      .catch((error) => Error(error))
      .finally(() => setLoading(false));
  }, [
    props.apiUrl,
    props.instrument,
    props.experimentNumber,
    props.userNumber,
    props.filename,
  ]);

  return (
    <ErrorBoundary FallbackComponent={Fallback}>
      {loading ? (
        <Stack
          spacing={2}
          sx={{
            justifyContent: "center",
            alignItems: "center",
            height: "100%",
            width: "100%",
          }}
        >
          <p>Finding your file</p>
          <CircularProgress />
        </Stack>
      ) : (
        <H5GroveProvider
          url={groveApiUrl}
          filepath={filepath}
          fetcher={fetcher}
          resetKeys={[filepath, token, groveApiUrl]}
        >
          <App propagateErrors />
        </H5GroveProvider>
      )}
    </ErrorBoundary>
  );
}
