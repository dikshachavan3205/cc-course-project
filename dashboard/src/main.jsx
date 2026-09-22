import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { ChronoProvider } from "./hooks/useChrono.js";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ChronoProvider>
        <App />
      </ChronoProvider>
    </BrowserRouter>
  </React.StrictMode>,
);