'use client';

import React, { useEffect, useState } from 'react';
import { useApp } from '@/lib/store';
import { Badge, Button, Card, CardHeader, InfoNote, Input, Modal, Select, Switch } from '@/components/ui/primitives';
import { ApiError } from '@/lib/api/client';
import {
  useCreateIndentTemplate, useDuplicateIndentTemplate, useIndentTemplates, usePharmacySettings, useUpdateIndentTemplate, useUpdatePharmacySettings,
  type MedicineOut, type PharmacySettingsOut,
} from '@/lib/api/pharmacy';
import { Copy, Plus, Settings as SettingsIcon } from 'lucide-react';

export function SettingsTab({ medicines, medicineNameById, canManage }: { medicines: MedicineOut[]; medicineNameById: Record<string, string>; canManage: boolean }) {
  return (
    <div className="animate-fade-up space-y-6 p-5">
      <PrintSettingsCard canManage={canManage} />
      <IndentTemplatesCard medicines={medicines} medicineNameById={medicineNameById} canManage={canManage} />
    </div>
  );
}

function PrintSettingsCard({ canManage }: { canManage: boolean }) {
  const { toast } = useApp();
  const settingsQuery = usePharmacySettings();
  const updateSettings = useUpdatePharmacySettings();
  const [form, setForm] = useState<PharmacySettingsOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (settingsQuery.data && !form) setForm(settingsQuery.data); }, [settingsQuery.data, form]);

  if (!form) return <Card className="p-6 text-center text-[13.5px] text-ink-500">Loading settings…</Card>;

  const set = (patch: Partial<PharmacySettingsOut>) => setForm((f) => (f ? { ...f, ...patch } : f));
  const toggles: { key: keyof PharmacySettingsOut; label: string }[] = [
    { key: 'show_gst', label: 'Show GST' }, { key: 'show_doctor', label: 'Show Doctor' }, { key: 'show_patient_details', label: 'Show Patient Details' },
    { key: 'show_batch', label: 'Show Batch' }, { key: 'show_expiry', label: 'Show Expiry' }, { key: 'show_mrp', label: 'Show MRP' }, { key: 'show_payment_info', label: 'Show Payment Info' },
  ];

  return (
    <Card>
      <CardHeader icon={<SettingsIcon className="h-4 w-4" />} title="Print Settings" subtitle="Used on pharmacy bills and printed invoices." />
      <div className="space-y-4 px-5 pb-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Pharmacy name" value={form.pharmacy_name} disabled={!canManage} onChange={(e) => set({ pharmacy_name: e.target.value })} />
          <Input label="GSTIN" value={form.gstin ?? ''} disabled={!canManage} onChange={(e) => set({ gstin: e.target.value })} />
          <Input label="Phone" value={form.phone ?? ''} disabled={!canManage} onChange={(e) => set({ phone: e.target.value })} />
          <Input label="Email" value={form.email ?? ''} disabled={!canManage} onChange={(e) => set({ email: e.target.value })} />
        </div>
        <Input label="Address" value={form.address ?? ''} disabled={!canManage} onChange={(e) => set({ address: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Invoice header</span>
            <textarea disabled={!canManage} className="min-h-[70px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900 disabled:bg-ink-50" value={form.invoice_header ?? ''} onChange={(e) => set({ invoice_header: e.target.value })} />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Invoice footer</span>
            <textarea disabled={!canManage} className="min-h-[70px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900 disabled:bg-ink-50" value={form.invoice_footer ?? ''} onChange={(e) => set({ invoice_footer: e.target.value })} />
          </label>
        </div>
        <div className="grid gap-3 border-t border-ink-100 pt-4 sm:grid-cols-2">
          {toggles.map((t) => (
            <div key={t.key} className="flex items-center justify-between rounded-lg border border-ink-100 px-3 py-2.5">
              <span className="text-[13.5px] text-ink-700">{t.label}</span>
              <Switch label={t.label} checked={!!form[t.key]} disabled={!canManage} onChange={(v) => set({ [t.key]: v } as Partial<PharmacySettingsOut>)} />
            </div>
          ))}
        </div>
        {canManage && (
          <div className="flex items-center justify-end gap-3 border-t border-ink-100 pt-4">
            {error && <p className="text-[13px] text-rose-600">{error}</p>}
            <Button
              variant="primary" loading={updateSettings.isPending}
              onClick={() => {
                setError(null);
                updateSettings.mutate(form, { onSuccess: () => toast({ title: 'Settings saved', tone: 'success' }), onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save settings.') });
              }}
            >
              Save Settings
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

function IndentTemplatesCard({ medicines, medicineNameById, canManage }: { medicines: MedicineOut[]; medicineNameById: Record<string, string>; canManage: boolean }) {
  const { toast } = useApp();
  const templatesQuery = useIndentTemplates();
  const updateTemplate = useUpdateIndentTemplate();
  const duplicateTemplate = useDuplicateIndentTemplate();
  const [addOpen, setAddOpen] = useState(false);
  const templates = templatesQuery.data ?? [];

  return (
    <Card>
      <CardHeader
        icon={<SettingsIcon className="h-4 w-4" />} title="Indent Templates" subtitle="Reusable structures for internal department requests — distinct from Medicine Templates."
        action={canManage && <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>New Indent Template</Button>}
      />
      <NewIndentTemplateModal open={addOpen} onClose={() => setAddOpen(false)} medicines={medicines} />
      <div className="space-y-2 px-5 pb-5">
        {templates.length === 0 ? (
          <InfoNote>No indent templates yet.</InfoNote>
        ) : (
          templates.map((t) => (
            <div key={t.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-ink-100 p-3">
              <div>
                <p className="text-[13.5px] font-semibold text-ink-900">{t.name} {t.department && <span className="tnum font-normal text-ink-400">· {t.department}{t.room ? ` / ${t.room}` : ''}</span>}</p>
                <p className="text-[12px] text-ink-500">{t.items.map((i) => `${medicineNameById[i.medicine_id] ?? 'Medicine'} × ${i.default_quantity}`).join(', ') || 'No medicines'}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={t.status === 'ACTIVE' ? 'completed' : 'neutral'} size="sm">{t.status === 'ACTIVE' ? 'Active' : 'Inactive'}</Badge>
                {canManage && (
                  <>
                    <Button size="sm" variant="ghost" icon={<Copy className="h-3.5 w-3.5" />} onClick={() => duplicateTemplate.mutate(t.id, { onSuccess: () => toast({ title: 'Template duplicated', tone: 'success' }) })}>Duplicate</Button>
                    <Button
                      size="sm" variant="ghost"
                      onClick={() => updateTemplate.mutate({ templateId: t.id, status: t.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' }, { onSuccess: () => toast({ title: t.status === 'ACTIVE' ? 'Deactivated' : 'Activated', tone: 'success' }) })}
                    >
                      {t.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function NewIndentTemplateModal({ open, onClose, medicines }: { open: boolean; onClose: () => void; medicines: MedicineOut[] }) {
  const { toast } = useApp();
  const createTemplate = useCreateIndentTemplate();
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('');
  const [room, setRoom] = useState('');
  const [lines, setLines] = useState<{ key: number; medicine_id: string; default_quantity: number }[]>([{ key: 0, medicine_id: '', default_quantity: 1 }]);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setName(''); setDepartment(''); setRoom(''); setLines([{ key: 0, medicine_id: '', default_quantity: 1 }]); setError(null); createTemplate.reset(); };
  const close = () => { reset(); onClose(); };
  const addLine = () => setLines((l) => [...l, { key: l.length ? Math.max(...l.map((x) => x.key)) + 1 : 0, medicine_id: '', default_quantity: 1 }]);
  const updateLine = (key: number, patch: Partial<{ medicine_id: string; default_quantity: number }>) => setLines((l) => l.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const removeLine = (key: number) => setLines((l) => (l.length > 1 ? l.filter((r) => r.key !== key) : l));

  return (
    <Modal
      open={open} onClose={close} title="New Indent Template"
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
                  { name: name.trim(), department: department.trim() || null, room: room.trim() || null, items: validLines.map((l) => ({ medicine_id: l.medicine_id, default_quantity: l.default_quantity })) },
                  { onSuccess: () => { close(); toast({ title: 'Indent template created', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not create the template.') }
                );
              }}
            >
              Create
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Input label="Template name" placeholder="OT Routine Restock" value={name} onChange={(e) => setName(e.target.value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Default department (optional)" value={department} onChange={(e) => setDepartment(e.target.value)} />
          <Input label="Default room (optional)" value={room} onChange={(e) => setRoom(e.target.value)} />
        </div>
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
              <button onClick={() => removeLine(line.key)} className="mt-2 text-[12px] font-medium text-rose-600 hover:text-rose-700">Remove line</button>
            </Card>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={addLine}>Add medicine</Button>
        </div>
      </div>
    </Modal>
  );
}
