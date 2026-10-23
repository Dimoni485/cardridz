import type { UserRole } from "./api/types";

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Администратор",
  editor: "Редактор",
  viewer: "Только чтение",
};

export const ROLE_HINTS: Record<UserRole, string> = {
  admin: "Полный доступ и управление пользователями",
  editor: "Просмотр и редактирование данных",
  viewer: "Просмотр данных и отчётов без изменений",
};
