import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';

export interface PermissionOut {
  id: string;
  code: string;
  module: string;
  description: string | null;
  is_critical: boolean;
}

export interface RoleOut {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_system_role: boolean;
  permissions: PermissionOut[];
}

export function useRoles() {
  return useQuery({
    queryKey: ['roles'],
    queryFn: () => apiFetch<RoleOut[]>('/roles'),
  });
}

export function usePermissionCatalogue() {
  return useQuery({
    queryKey: ['role-permissions-catalogue'],
    queryFn: () => apiFetch<PermissionOut[]>('/roles/permissions'),
  });
}

export function useUpdateRolePermissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ roleId, permissionIds }: { roleId: string; permissionIds: string[] }) =>
      apiFetch<RoleOut>(`/roles/${roleId}/permissions`, {
        method: 'PUT',
        body: { permission_ids: permissionIds },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] }),
  });
}
