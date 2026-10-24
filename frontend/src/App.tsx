import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Spinner } from "./components/ui";
import { CartridgeDetailPage } from "./pages/CartridgeDetailPage";
import { CartridgesPage } from "./pages/CartridgesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { EntitiesPage } from "./pages/EntitiesPage";
import { HelpPage } from "./pages/HelpPage";
import { InvoiceDetailPage } from "./pages/InvoiceDetailPage";
import { InvoicesPage } from "./pages/InvoicesPage";
import { LoginPage } from "./pages/LoginPage";
import { ModelsPage } from "./pages/ModelsPage";
import { PartDetailPage } from "./pages/PartDetailPage";
import { PartReplacementsPage } from "./pages/PartReplacementsPage";
import { PartRequestsPage } from "./pages/PartRequestsPage";
import { PartsPage } from "./pages/PartsPage";
import { OperationsPage } from "./pages/OperationsPage";
import { PrinterModelsPage } from "./pages/PrinterModelsPage";
import { PrintersPage } from "./pages/PrintersPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ServiceProvidersPage } from "./pages/ServiceProvidersPage";
import { UsersPage } from "./pages/UsersPage";

export function App() {
  const { user, loading, isAdmin } = useAuth();

  if (loading) {
    return (
      <div className="app-loading">
        <Spinner label="Проверка авторизации…" />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="cartridges" element={<CartridgesPage />} />
        <Route path="cartridges/:id" element={<CartridgeDetailPage />} />
        <Route path="operations" element={<OperationsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="printers" element={<PrintersPage />} />
        <Route path="parts" element={<PartsPage />} />
        <Route path="parts/:id" element={<PartDetailPage />} />
        <Route path="replacements" element={<PartReplacementsPage />} />
        <Route path="part-requests" element={<PartRequestsPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="printer-models" element={<PrinterModelsPage />} />
        <Route path="employees" element={<EmployeesPage />} />
        <Route path="entities" element={<EntitiesPage />} />
        <Route path="service-providers" element={<ServiceProvidersPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="help" element={<HelpPage />} />
        <Route
          path="users"
          element={isAdmin ? <UsersPage /> : <Navigate to="/" replace />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
