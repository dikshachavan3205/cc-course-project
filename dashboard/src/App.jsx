import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout.jsx";
import { ErrorBoundary } from "./components/ErrorBoundary.jsx";
import Overview from "./pages/Overview.jsx";
import OverviewTimeline from "./pages/OverviewTimeline.jsx";
import Instances from "./pages/Instances.jsx";
import Checkpoints from "./pages/Checkpoints.jsx";
import Migrations from "./pages/Migrations.jsx";
import Monitoring from "./pages/Monitoring.jsx";
import Simulate from "./pages/Simulate.jsx";
import Settings from "./pages/Settings.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<Navigate to="/overview" replace />} />
        <Route
          path="overview"
          element={
            <ErrorBoundary>
              <Overview />
            </ErrorBoundary>
          }
        />
        <Route
          path="overview/timeline"
          element={
            <ErrorBoundary>
              <OverviewTimeline />
            </ErrorBoundary>
          }
        />
        <Route
          path="instances"
          element={
            <ErrorBoundary>
              <Instances />
            </ErrorBoundary>
          }
        />
        <Route
          path="checkpoints"
          element={
            <ErrorBoundary>
              <Checkpoints />
            </ErrorBoundary>
          }
        />
        <Route
          path="migrations"
          element={
            <ErrorBoundary>
              <Migrations />
            </ErrorBoundary>
          }
        />
        <Route
          path="monitoring"
          element={
            <ErrorBoundary>
              <Monitoring />
            </ErrorBoundary>
          }
        />
        <Route
          path="simulate"
          element={
            <ErrorBoundary>
              <Simulate />
            </ErrorBoundary>
          }
        />
        <Route
          path="settings"
          element={
            <ErrorBoundary>
              <Settings />
            </ErrorBoundary>
          }
        />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Route>
    </Routes>
  );
}