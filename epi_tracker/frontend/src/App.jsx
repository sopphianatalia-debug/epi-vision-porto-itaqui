import React, { useState, useCallback } from "react";
import { Layout } from "./components/Layout.jsx";
import { Dashboard } from "./pages/Dashboard.jsx";
import { AreasMap } from "./pages/AreasMap.jsx";
import { Employees } from "./pages/Employees.jsx";
import { PPEList } from "./pages/PPEList.jsx";
import { Trackers } from "./pages/Trackers.jsx";
import { Areas, Checkpoints } from "./pages/Areas.jsx";
import { Inconsistencies } from "./pages/Inconsistencies.jsx";
import { History } from "./pages/History.jsx";
import { Simulation } from "./pages/Simulation.jsx";
import { Toast } from "./components/Common.jsx";
import { usePolling } from "./hooks/usePolling.js";
import { Alerts } from "./pages/Alerts.jsx";
import { Cameras } from "./pages/Cameras.jsx";
import { api, alertsApi } from "./services/api.js";

function getRouteFromHash() {
  const h = window.location.hash.replace("#", "");
  return h || "dashboard";
}

async function fetchAll() {
  const [trackers, areas, employees, ppeList, checkpoints, inconsistencies, events] = await Promise.all([
    api.listTrackers(),
    api.listAreas(),
    api.listEmployees(),
    api.listPPE(),
    api.listCheckpoints(),
    api.listInconsistencies(),
    api.listEvents(200),
  ]);
  return { trackers, areas, employees, ppeList, checkpoints, inconsistencies, events };
}

// Alertas vêm de um serviço separado. Se ele estiver fora do ar, só esta parte
// mostra "indisponível" — o resto da interface não é afetado.
async function fetchAlerts() {
  try {
    const [summary, alerts] = await Promise.all([alertsApi.summary(), alertsApi.list(true)]);
    return { offline: false, summary, alerts };
  } catch (e) {
    return { offline: true, summary: null, alerts: null };
  }
}

export function App() {
  const [route, setRoute] = useState(getRouteFromHash());
  const [toast, setToast] = useState(null);

  const { data, error, loading, lastUpdated, refresh } = usePolling(fetchAll, 4000, []);

  const alertsPoll = usePolling(fetchAlerts, 4000, []);
  const alertsData = alertsPoll.data;

  const navigate = useCallback((key) => {
    window.location.hash = key;
    setRoute(key);
  }, []);

  window.onhashchange = () => setRoute(getRouteFromHash());

  const notify = useCallback((message, kind) => {
    setToast({ message, kind: kind || "success" });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const apiOnline = !error;

  const trackerLocations = {};
  if (data) {
    data.trackers.forEach((t) => {
      trackerLocations[t.tracker_id] = { area_id: t.last_area_id, state: t.status };
    });
  }

  const commonProps = {
    loading,
    error,
    onRetry: refresh,
    onActionDone: refresh,
    notify,
  };

  let page = null;
  if (route === "dashboard") {
    page = <Dashboard {...commonProps} trackers={data && data.trackers} employees={data && data.employees}
      inconsistencies={data && data.inconsistencies} events={data && data.events} areas={data && data.areas}
      ppeList={data && data.ppeList} checkpoints={data && data.checkpoints} onNavigate={navigate} />;
  } else if (route === "map") {
    page = <AreasMap {...commonProps} areas={data && data.areas} employees={data && data.employees}
      trackers={data && data.trackers} ppeList={data && data.ppeList} checkpoints={data && data.checkpoints} />;
  } else if (route === "employees") {
    page = <Employees {...commonProps} employees={data && data.employees} />;
  } else if (route === "ppe") {
    page = <PPEList {...commonProps} ppeList={data && data.ppeList} trackerLocations={trackerLocations} />;
  } else if (route === "trackers") {
    page = <Trackers {...commonProps} trackers={data && data.trackers} ppeList={data && data.ppeList} />;
  } else if (route === "areas") {
    page = <Areas {...commonProps} areas={data && data.areas} employees={data && data.employees}
      trackers={data && data.trackers} ppeList={data && data.ppeList} checkpoints={data && data.checkpoints} />;
  } else if (route === "checkpoints") {
    page = <Checkpoints {...commonProps} checkpoints={data && data.checkpoints} />;
  } else if (route === "alerts") {
    page = <Alerts alerts={alertsData && alertsData.alerts} summary={alertsData && alertsData.summary}
      offline={alertsData && alertsData.offline} loading={alertsPoll.loading}
      onChanged={alertsPoll.refresh} notify={notify} />;
  } else if (route === "cameras") {
    page = <Cameras />;
  } else if (route === "inconsistencies") {
    page = <Inconsistencies {...commonProps} inconsistencies={data && data.inconsistencies} />;
  } else if (route === "history") {
    page = <History {...commonProps} events={data && data.events} />;
  } else if (route === "simulation") {
    page = <Simulation {...commonProps} trackers={data && data.trackers} areas={data && data.areas} />;
  }

  return (
    <Layout route={route} onNavigate={navigate} apiOnline={apiOnline} lastUpdated={lastUpdated}
      alertCount={alertsData && alertsData.summary ? alertsData.summary.open_total : 0}
      alertCritical={alertsData && alertsData.summary ? alertsData.summary.by_severity.CRITICAL : 0}>
      {page}
      {toast && <Toast message={toast.message} kind={toast.kind} onClose={() => setToast(null)} />}
    </Layout>
  );
}
