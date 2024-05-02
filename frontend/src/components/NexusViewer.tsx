"use client";
import "@h5web/app/dist/styles.css";
import { App, H5GroveProvider } from "@h5web/app";
import { useMemo } from "react";

export default function NexusViewer(props: {
  filepath: string;
  apiUrl: string;
}) {
  return (
    <H5GroveProvider
      url={props.apiUrl}
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
