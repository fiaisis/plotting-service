"use client";
import { useEffect, useState } from "react";

const TokenRefresh = () => {
  const [refreshCount, setRefreshCount] = useState<number>(0);
  useEffect(() => {
    const refreshToken = () => {
      setRefreshCount(refreshCount + 1);
      const token = localStorage.getItem("scigateway:token");
      fetch("/auth/api/jwt/refresh", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token: token }),
      })
        .then((response) => response.json())
        .then((data) => localStorage.setItem("scigateway:token", data.token))
        .catch((_) => console.error("Could not refresh token"));
    };

    refreshToken();
    // Set up the interval to refresh the token every 10 minutes (600000 milliseconds)
    const intervalId = setInterval(refreshToken, 600000);

    // Set up the timeout to clear the interval after 12 hours (43200000 milliseconds)
    const timeoutId = setTimeout(() => {
      clearInterval(intervalId);
    }, 43200000);

    // Clear the interval and timeout when the component unmounts
    return () => {
      clearInterval(intervalId);
      clearTimeout(timeoutId);
    };
  });

  return <></>;
};

export default TokenRefresh;
