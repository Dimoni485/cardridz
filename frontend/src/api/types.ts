export type CartridgeStatus =
  | "in_stock"
  | "issued"
  | "installed"
  | "in_refill"
  | "in_restore"
  | "written_off";

export type OperationType =
  | "receipt"
  | "issue"
  | "install"
  | "uninstall"
  | "return"
  | "send_refill"
  | "refill_done"
  | "send_restore"
  | "restore_done"
  | "write_off";

export type CartridgeKind = "original" | "compatible";
export type CartridgeColor = "black" | "cyan" | "magenta" | "yellow" | "other";
export type PrinterStatus = "active" | "repair" | "retired";
export type ServiceResult =
  | "refilled"
  | "restored"
  | "repaired"
  | "failed"
  | "unrepairable"
  | "other";

export type PrinterRepairStatus = "in_service" | "returned";

export type UserRole = "admin" | "editor" | "viewer";

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  can_edit: boolean;
  is_admin: boolean;
}

export interface AdminUser {
  id: number;
  username: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  can_edit: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LegalEntityBrief {
  id: number;
  name: string;
}

export interface DepartmentBrief {
  id: number;
  name: string;
  room: string | null;
  legal_entity: LegalEntityBrief;
}

export interface Department {
  id: number;
  legal_entity_id: number;
  name: string;
  room: string | null;
  is_active: boolean;
  legal_entity: LegalEntityBrief;
  created_at: string;
  updated_at: string;
}

export interface LegalEntity {
  id: number;
  name: string;
  inn: string | null;
  is_active: boolean;
  notes: string | null;
  departments: DepartmentBrief[];
  created_at: string;
  updated_at: string;
}

export interface ServiceProvider {
  id: number;
  name: string;
  inn: string | null;
  contact_person: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServiceProviderBrief {
  id: number;
  name: string;
}

export interface Employee {
  id: number;
  full_name: string;
  department_id: number | null;
  department: DepartmentBrief | null;
  position: string | null;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmployeeBrief {
  id: number;
  full_name: string;
  department: DepartmentBrief | null;
  position: string | null;
}

export interface PrinterModel {
  id: number;
  vendor: string;
  name: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CartridgeModel {
  id: number;
  vendor: string;
  name: string;
  kind: CartridgeKind;
  color: CartridgeColor;
  resource_pages: number | null;
  refillable: boolean;
  min_stock: number;
  notes: string | null;
  printer_models: PrinterModel[];
  created_at: string;
  updated_at: string;
}

export interface CartridgeModelBrief {
  id: number;
  vendor: string;
  name: string;
  color: CartridgeColor;
  kind: CartridgeKind;
  refillable: boolean;
}

export interface Printer {
  id: number;
  inventory_no: string;
  serial_no: string | null;
  model_id: number;
  location: string | null;
  ip_address: string | null;
  department_id: number | null;
  employee_id: number | null;
  status: PrinterStatus;
  notes: string | null;
  model: PrinterModel;
  department: DepartmentBrief | null;
  employee: EmployeeBrief | null;
  service_provider: ServiceProviderBrief | null;
  service_since: string | null;
  expected_return_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface PrinterRepair {
  id: number;
  printer_id: number;
  status: PrinterRepairStatus;
  sent_at: string;
  expected_return_date: string | null;
  returned_at: string | null;
  document_no: string | null;
  cost: number | null;
  result: ServiceResult | null;
  service_provider: ServiceProviderBrief | null;
  legal_entity: LegalEntityBrief | null;
  department: DepartmentBrief | null;
  user: { id: number; username: string; full_name: string } | null;
  comment: string | null;
  created_at: string;
}

export interface PrinterBrief {
  id: number;
  inventory_no: string;
  location: string | null;
  model: { id: number; vendor: string; name: string };
}

export interface Cartridge {
  id: number;
  inventory_no: string;
  serial_no: string | null;
  status: CartridgeStatus;
  model: CartridgeModelBrief;
  employee: EmployeeBrief | null;
  printer: PrinterBrief | null;
  service_provider: ServiceProviderBrief | null;
  service_since: string | null;
  expected_return_date: string | null;
  purchase_price: number | null;
  purchase_date: string | null;
  refill_count: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Operation {
  id: number;
  cartridge_id: number;
  cartridge: { id: number; inventory_no: string; model: CartridgeModelBrief };
  type: OperationType;
  from_status: CartridgeStatus | null;
  to_status: CartridgeStatus;
  employee: EmployeeBrief | null;
  printer: PrinterBrief | null;
  legal_entity: LegalEntityBrief | null;
  department: DepartmentBrief | null;
  service_provider: ServiceProviderBrief | null;
  expected_return_date: string | null;
  result: ServiceResult | null;
  user: { id: number; username: string; full_name: string } | null;
  cost: number | null;
  document_no: string | null;
  comment: string | null;
  occurred_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface SummaryStats {
  total_cartridges: number;
  total_models: number;
  total_printers: number;
  total_employees: number;
  by_status: Record<CartridgeStatus, number>;
  low_stock: {
    model_id: number;
    vendor: string;
    name: string;
    color: CartridgeColor;
    in_stock: number;
    min_stock: number;
    shortage: number;
  }[];
  recent_operations: Operation[];
}

export interface StockRow {
  model_id: number;
  vendor: string;
  name: string;
  color: CartridgeColor;
  kind: CartridgeKind;
  resource_pages: number | null;
  min_stock: number;
  in_stock: number;
  issued: number;
  installed: number;
  in_refill: number;
  in_restore: number;
  written_off: number;
  total: number;
  refills: number;
}

export interface StockReport {
  rows: StockRow[];
  totals: Record<string, number>;
}

export interface OperationsReport {
  date_from: string;
  date_to: string;
  total_operations: number;
  total_cost: number;
  by_type: { type: OperationType; count: number; cost: number }[];
  by_day: { day: string; count: number }[];
}

export interface EmployeesReport {
  rows: {
    employee_id: number;
    full_name: string;
    department: string | null;
    legal_entity: string | null;
    is_active: boolean;
    issued: number;
    installed_at_printers: number;
    total: number;
  }[];
}

export interface UsageRow {
  legal_entity_id: number | null;
  legal_entity_name: string | null;
  department_id: number | null;
  department_name: string | null;
  issued_count: number;
  cartridges_cost: number;
  service_cost: number;
  repair_cost: number;
  total_cost: number;
}

export interface UsageEntityRow {
  legal_entity_id: number | null;
  legal_entity_name: string | null;
  issued_count: number;
  cartridges_cost: number;
  service_cost: number;
  repair_cost: number;
  total_cost: number;
}

export interface UsageTotals {
  issued_count: number;
  cartridges_cost: number;
  service_cost: number;
  repair_cost: number;
  total_cost: number;
}

export interface UsageReport {
  year: number;
  month: number;
  date_from: string;
  date_to: string;
  rows: UsageRow[];
  by_legal_entity: UsageEntityRow[];
  totals: UsageTotals;
}


export interface ServiceProviderStat {
  provider_id: number | null;
  provider_name: string | null;
  sent_count: number;
  returned_count: number;
  cost: number;
  outstanding_count: number;
  printer_cost: number;
  printer_sent_count: number;
  printer_returned_count: number;
  printer_outstanding_count: number;
}

export interface ServiceOutstandingRow {
  cartridge_id: number;
  inventory_no: string;
  model_name: string;
  status: CartridgeStatus;
  provider_id: number | null;
  provider_name: string | null;
  service_since: string | null;
  expected_return_date: string | null;
  overdue: boolean;
}

export interface PrinterOutstandingRow {
  printer_id: number;
  inventory_no: string;
  model_name: string;
  provider_id: number | null;
  provider_name: string | null;
  service_since: string | null;
  expected_return_date: string | null;
  overdue: boolean;
}

export interface ServiceReport {
  year: number;
  month: number;
  date_from: string;
  date_to: string;
  rows: ServiceProviderStat[];
  totals: {
    sent_count: number;
    returned_count: number;
    cost: number;
    outstanding_count: number;
    printer_sent_count: number;
    printer_returned_count: number;
    printer_cost: number;
    printer_outstanding_count: number;
  };
  outstanding: ServiceOutstandingRow[];
  printers_outstanding: PrinterOutstandingRow[];
}
