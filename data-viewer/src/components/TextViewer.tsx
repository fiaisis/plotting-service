"use client";
import { useEffect, useState } from "react";

const TextViewer = (props: {
  filename: string;
  instrument: string;
  experimentNumber: string;
  apiUrl: string;
}) => {
  const [text, setText] = useState<string>("loading...");

  useEffect(() => {
    const token = localStorage.getItem("scigateway:token") ?? "";
    fetch(
      `${props.apiUrl}/text/instrument/${props.instrument}/experiment_number/${props.experimentNumber}?filename=${props.filename}`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      },
    )
      .then((res) => {
        if (!res.ok) {
          throw new Error(res.statusText);
        }
        return res.text();
      })
      .then((resultText) => setText(resultText))
      .catch((_) => setText("something went wrong"));
  }, []);

  return (
    <div>
      <pre>{text}</pre>
    </div>
  );
};

export default TextViewer;
