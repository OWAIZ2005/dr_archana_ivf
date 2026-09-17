import type { Role, StaffUser } from './data';
import type { UserSummary } from './api/types';

/**
 * The backend's permission taxonomy has 10 role codes (see
 * backend/app/roles/seed.py); this UI was designed around 4 broad
 * personas. Every seeded demo account maps directly; any other backend
 * role code falls back to 'management' (the broadest nav visibility)
 * rather than hiding the whole app behind an unmapped role.
 */
const ROLE_CODE_MAP: Record<string, Role> = {
  doctor: 'doctor',
  receptionist: 'receptionist',
  embryologist: 'embryologist',
  management: 'management',
  administrator: 'management',
  it_administrator: 'management',
  pharmacist: 'pharmacist',
};

export function mapRoleCode(roleCode: string): Role {
  return ROLE_CODE_MAP[roleCode] ?? 'management';
}

const ROLE_META: Record<Role, { title: string; accent: string }> = {
  doctor: { title: 'Chief Consultant & IVF Specialist', accent: 'from-emerald-500 to-teal-600' },
  receptionist: { title: 'Front Office Executive', accent: 'from-sky-500 to-blue-600' },
  embryologist: { title: 'Senior Clinical Embryologist', accent: 'from-violet-500 to-purple-600' },
  management: { title: 'Hospital Administrator', accent: 'from-amber-500 to-orange-600' },
  pharmacist: { title: 'Pharmacist-in-Charge', accent: 'from-rose-500 to-pink-600' },
};

function initialsOf(fullName: string): string {
  const parts = fullName.split(' ').filter(Boolean);
  return parts.slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?';
}

/** Builds the same StaffUser shape the UI already renders (Sidebar,
 * Topbar, Access) from the real authenticated user, so those components
 * needed no restructuring — only their data source changed. */
export function toDisplayUser(user: UserSummary): StaffUser {
  const role = mapRoleCode(user.role_code);
  const meta = ROLE_META[role];
  return {
    id: user.employee_code,
    role,
    name: user.full_name,
    title: meta.title,
    initials: initialsOf(user.full_name),
    email: user.email,
    department: user.department ?? '',
    accent: meta.accent,
  };
}
