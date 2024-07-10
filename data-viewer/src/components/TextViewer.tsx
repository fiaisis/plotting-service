"use client";
const getText = async (url: string) => {
  return await fetch(url)
    .then((res) => {
      if (!res.ok) {
        throw new Error(res.statusText);
      }
      return res.text();
    })
    .catch((_) => "something went wrong");
};

const TextViewer = async (props: {
  filename: string;
  instrument: string;
  experimentNumber: string;
  apiUrl: string;
}) => {
  const text = await getText(
    `${props.apiUrl}/text/instrument/${props.instrument}/experiment_number/${props.experimentNumber}?filename=${props.filename}`,
  );
  return (
    <div>
      <pre>{text}</pre>
    </div>
  );
};

export default TextViewer;
