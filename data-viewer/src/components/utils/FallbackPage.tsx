import Image from "next/image";

export const Fallback = () => (
  <div
    style={{
      display: "flex",
      justifyContent: "center",
      alignItems: "center",
      flexDirection: "column",
      height: "100vh",
    }}
  >
    <Image
      src={"/monkey.webp"}
      unoptimized
      alt={"Monkey holding excellent website award"}
      height={256}
      width={256}
      style={{ height: "50%", width: "30%" }}
    />
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
