"use client";
import { useEffect } from "react";

const TokenRefresh = () => {
  useEffect(() => {
    // Function to send the POST request
    const token = localStorage.getItem("scigateway:token");
    fetch("/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ token: token }),
    }).catch((e) => console.error(e));
  }, []);

  return <></>;
};

export default TokenRefresh;
