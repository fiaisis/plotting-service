"use client";
import { useEffect } from "react";

const TokenRefresh = () => {
  useEffect(() => {
    const token = localStorage.getItem("scigateway:token");
    fetch("/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ token: token }),
    })
      .then((response) => response.json())
      .then((data) => localStorage.setItem("scigateway:token", data.token))
      .catch((_) => console.error("Could not refresh token"));
  }, []);

  return <></>;
};

export default TokenRefresh;
