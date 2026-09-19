'use client';

import React, { useMemo, useState } from 'react';
import { useApp } from '@/lib/store';
import { Badge, Button, Card, Field, InfoNote, Input, Modal, RemoveLineButton, Select } from '@/components/ui/primitives';
import { ApiError } from '@/lib/api/client';
import {
  useAddTemplateItem, useCreateTemplate, useRemoveTemplateItem, useTemplate, useTemplates, useUpdateTemplate, useUpdateTemplateItem,
  type MedicineOut, type TemplateStatus,
} from '@/lib/api/pharmacy';
import { Plus, Search, Trash2 } from 'lucide-react';

export function TemplatesTab({ medicines, medicineNameById, canManage }: { medicines: MedicineOut[]; medicineNameById: Record<string, string>; canManage: boolean }) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'' | TemplateStatus>('');
  const [addOpen, setAddOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const templatesQuery = useTemplates({ search: search || undefined, status: statusFilter || undefined });
  const templates = templatesQuery.data ?? [];

  return (
    <div className="animate-fade-up space-y-4 p-5">
      <TemplateFormModal open={addOpen} onClose={() => setAddOpen(false)} medicines={medicines} />
      {detailId && <TemplateDetailModal templateId={detailId} medicines={medicines} medicineNameById={medicineNameById} canManage={canManage} onClose={() => setDetailId(null)} />}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-64">
            <Input label="Search" icon={<Search className="h-3.5 w-3.5" />} placeholder="OT Kit, Emergency Kit…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="w-40">
            <Select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as '' | TemplateStatus)}>
              <option value="">All</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </Select>
          </div>
        </div>
        {canManage && (
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>New Template</Button>
        )}
      </div>

      {templatesQuery.isLoading ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading templates…</p>
      ) : templates.length === 0 ? (
        <InfoNote>No templates match. {canManage && 'Use "New Template" to create a reusable medicine kit.'}</InfoNote>
      ) : (
        <div className="stagger grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {templates.map((t) => (
            <Card key={t.id} className="p-4" interactive onClick={() => setDetailId(t.id)}>
              <div className="flex items-center justify-between">
                <p className="text-[14px] font-semibold text-ink-900">{t.name}</p>
                <Badge tone={t.status === 'ACTIVE' ? 'completed' : 'neutral'} size="sm">{t.status === 'ACTIVE' ? 'Active' : 'Inactive'}</Badge>
              </div>
              {t.description && <p className="mt-1 text-[12.5px] text-ink-500">{t.description}</p>}
              <p className="mt-2 text-[12px] text-ink-400">{t.items.length} medicine{t.items.length === 1 ? '' : 's'}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function TemplateFormModal({ open, onClose, medicines }: { open: boolean; onClose: () => void; medicines: MedicineOut[] }) {
  const { toast } = useApp();
  const createTemplate = useCreateTemplate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [lines, setLines] = useState<{ key: number; medicine_id: string; default_quantity: number }[]>([{ key: 0, medicine_id: '', default_quantity: 1 }]);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setName(''); setDescription(''); setLines([{ key: 0, medicine_id: '', default_quantity: 1 }]); setError(null); createTemplate.reset(); };
  const close = () => { reset(); onClose(); };
  const addLine = () => setLines((l) => [...l, { key: l.length ? Math.max(...l.map((x) => x.key)) + 1 : 0, medicine_id: '', default_quantity: 1 }]);
  const updateLine = (key: number, patch: Partial<{ medicine_id: string; default_quantity: number }>) => setLines((l) => l.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const removeLine = (key: number) => setLines((l) => (l.length > 1 ? l.filter((r) => r.key !== key) : l));

  return (
    <Modal
      open={open} onClose={close} title="New Medicine Template" subtitle="A reusable kit — e.g. OT Kit, Emergency Kit."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary" disabled={!name.trim() || createTemplate.isPending} loading={createTemplate.isPending}
              onClick={() => {
                setError(null);
                const validLines = lines.filter((l) => l.medicine_id && l.default_quantity > 0);
                createTemplate.mutate(
                  { name: name.trim(), description: description.trim() || null, items: validLines.map((l) => ({ medicine_id: l.medicine_id, default_quantity: l.default_quantity })) },
                  { onSuccess: () => { close(); toast({ title: 'Template created', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not create the template.') }
                );
              }}
            >
              Create Template
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Input label="Template name" placeholder="OT Kit" value={name} onChange={(e) => setName(e.target.value)} />
        <Input label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className="space-y-2.5">
          {lines.map((line) => (
            <Card key={line.key} className="p-3">
              <div className="grid gap-2.5 sm:grid-cols-[2fr_1fr]">
                <Select label="Medicine" value={line.medicine_id} onChange={(e) => updateLine(line.key, { medicine_id: e.target.value })}>
                  <option value="">Select…</option>
                  {medicines.map((m) => <option key={m.id} value={m.id}>{m.brand_name ?? m.generic_name}</option>)}
                </Select>
                <Input label="Default qty" type="number" min={1} value={String(line.default_quantity)} onChange={(e) => updateLine(line.key, { default_quantity: Number(e.target.value) || 0 })} />
              </div>
              <RemoveLineButton label="Remove line" onClick={() => removeLine(line.key)} />
            </Card>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={addLine}>Add medicine</Button>
        </div>
      </div>
    </Modal>
  );
}

function TemplateDetailModal({
  templateId, medicines, medicineNameById, canManage, onClose,
}: { templateId: string; medicines: MedicineOut[]; medicineNameById: Record<string, string>; canManage: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const templateQuery = useTemplate(templateId);
  const updateTemplate = useUpdateTemplate();
  const addItem = useAddTemplateItem();
  const updateItem = useUpdateTemplateItem();
  const removeItem = useRemoveTemplateItem();
  const [newMedicineId, setNewMedicineId] = useState('');
  const [newQty, setNewQty] = useState('1');
  const [editingQty, setEditingQty] = useState<Record<string, string>>({});
  // Removing a template item is permanent and one click away, right next to
  // a quantity field people click near constantly — require a second click
  // to confirm instead of a native confirm() (which can throw in some
  // embedded browser contexts, same failure mode as window.prompt()).
  const [confirmingItemId, setConfirmingItemId] = useState<string | null>(null);

  const template = templateQuery.data;
  const availableMedicines = useMemo(() => {
    if (!template) return medicines;
    const used = new Set(template.items.map((i) => i.medicine_id));
    return medicines.filter((m) => !used.has(m.id));
  }, [medicines, template]);

  return (
    <Modal
      open onClose={onClose} title={template?.name ?? 'Template'} subtitle={template?.description ?? undefined}
      footer={
        <div className="flex items-center justify-between gap-3">
          <Badge tone={template?.status === 'ACTIVE' ? 'completed' : 'neutral'} size="sm">{template?.status === 'ACTIVE' ? 'Active' : 'Inactive'}</Badge>
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={onClose}>Close</Button>
            {canManage && template && (
              <Button
                variant="secondary"
                onClick={() => updateTemplate.mutate(
                  { templateId, status: template.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' },
                  { onSuccess: () => toast({ title: template.status === 'ACTIVE' ? 'Template deactivated' : 'Template activated', tone: 'success' }) }
                )}
              >
                {template.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
              </Button>
            )}
          </div>
        </div>
      }
    >
      {!template ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div className="space-y-2">
            {template.items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 rounded-xl border border-ink-100 p-3">
                <p className="flex-1 text-[13.5px] font-medium text-ink-900">{medicineNameById[item.medicine_id] ?? 'Medicine'}</p>
                {canManage ? (
                  <>
                    <Input
                      type="number" min={1} className="w-20" value={editingQty[item.id] ?? String(item.default_quantity)}
                      onChange={(e) => setEditingQty((prev) => ({ ...prev, [item.id]: e.target.value }))}
                      onBlur={(e) => {
                        const qty = Number(e.target.value) || 0;
                        if (qty > 0 && qty !== item.default_quantity) updateItem.mutate({ templateId, itemId: item.id, quantity: qty });
                      }}
                    />
                    {confirmingItemId === item.id ? (
                      <Button
                        size="sm" variant="danger" loading={removeItem.isPending}
                        onClick={() => removeItem.mutate({ templateId, itemId: item.id }, { onSettled: () => setConfirmingItemId(null) })}
                      >
                        Confirm remove?
                      </Button>
                    ) : (
                      <button
                        onClick={() => setConfirmingItemId(item.id)}
                        aria-label={`Remove ${medicineNameById[item.medicine_id] ?? 'medicine'} from this template`}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </>
                ) : (
                  <span className="tnum text-[13px] text-ink-600">{item.default_quantity}</span>
                )}
              </div>
            ))}
            {template.items.length === 0 && <InfoNote>No medicines on this template yet.</InfoNote>}
          </div>

          {canManage && (
            <div className="flex items-end gap-2 border-t border-ink-100 pt-4">
              <div className="flex-1">
                <Select label="Add medicine" value={newMedicineId} onChange={(e) => setNewMedicineId(e.target.value)}>
                  <option value="">Select…</option>
                  {availableMedicines.map((m) => <option key={m.id} value={m.id}>{m.brand_name ?? m.generic_name}</option>)}
                </Select>
              </div>
              <Input label="Qty" type="number" min={1} className="w-20" value={newQty} onChange={(e) => setNewQty(e.target.value)} />
              <Button
                variant="secondary" disabled={!newMedicineId} loading={addItem.isPending}
                onClick={() => addItem.mutate(
                  { templateId, medicine_id: newMedicineId, default_quantity: Number(newQty) || 1 },
                  { onSuccess: () => { setNewMedicineId(''); setNewQty('1'); } }
                )}
              >
                Add
              </Button>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
