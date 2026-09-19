'use client';

import React, { useState } from 'react';
import { useApp } from '@/lib/store';
import { cn, ageFromDOB, initialsOf } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, SectionTitle, Input, Select, Field, InfoNote, Avatar } from '@/components/ui/primitives';
import { useCreateCouple, useUploadPatientDocument, useMandatoryDocumentStatus, uploadPatientDocument } from '@/lib/api/patients';
import { PhotoCapture } from '@/components/ui/PhotoCapture';
import { SignatureCapture } from '@/components/ui/SignatureCapture';
import { ApiError } from '@/lib/api/client';
import type { CoupleOut } from '@/lib/api/types';
import { Check, ChevronLeft, ChevronRight, UserPlus, Users, Heart, FileCheck, Link2, ShieldCheck, Sparkles, AlertTriangle, Upload } from 'lucide-react';

const STEPS = [
  { id: 0, label: 'Patient Details', icon: UserPlus },
  { id: 1, label: 'Partner Details', icon: Users },
  { id: 2, label: 'Fertility History', icon: Heart },
  { id: 3, label: 'Documents & Consent', icon: FileCheck },
  { id: 4, label: 'Review & Create', icon: Check },
];

/** New requirement — mandatory document upload right after registration:
 * Aadhaar for Indian patients, visa for international ones (source doc §4). */
function MandatoryDocumentUpload({ patientId, patientName, isInternational }: { patientId: string; patientName: string; isInternational: boolean }) {
  const { toast } = useApp();
  const upload = useUploadPatientDocument();
  const statusQuery = useMandatoryDocumentStatus(patientId);
  const documentType = isInternational ? 'visa' : 'aadhaar';
  const label = isInternational ? 'Visa' : 'Aadhaar';

  return (
    <div>
      <div className="mb-3 flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
          <ShieldCheck className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[14.5px] font-semibold text-ink-900">{label} required for {patientName}</p>
          <p className="text-[12.5px] text-ink-500">{isInternational ? 'International patients must provide a valid visa.' : 'Aadhaar is mandatory for Indian patients.'}</p>
        </div>
      </div>

      {statusQuery.data?.is_uploaded ? (
        <Badge tone="completed" size="sm">{label} uploaded{statusQuery.data.is_verified ? ' and verified' : ' — pending verification'}</Badge>
      ) : (
        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-ink-300 p-5 text-[13.5px] text-ink-500 transition-colors hover:border-brand-400 hover:text-brand-700">
          <Upload className="h-4 w-4" />
          {upload.isPending ? 'Uploading…' : `Upload ${label}`}
          <input
            type="file"
            className="hidden"
            accept="image/*,.pdf"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              upload.mutate(
                { patientId, documentType, file },
                { onSuccess: () => toast({ title: `${label} uploaded`, body: 'Awaiting front-desk verification.', tone: 'success' }) }
              );
            }}
          />
        </label>
      )}
    </div>
  );
}

/** Small review-screen thumbnail: the captured photo if there is one, else the
 * initials avatar, so the reviewer can see exactly which face is attached to
 * which person before the couple is created. */
function ReviewPhoto({ file, initials, gradient }: { file: File | null; initials: string; gradient: string }) {
  const [url, setUrl] = useState<string | null>(null);
  React.useEffect(() => {
    if (!file) { setUrl(null); return; }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  if (url) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="Registration photo preview" className="h-10 w-10 rounded-full object-cover ring-1 ring-ink-200" />;
  }
  return <Avatar initials={initials} size="md" gradient={gradient} />;
}

export function Registration() {
  const { go, toast, openPatient } = useApp();
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(false);
  const [createdCouple, setCreatedCouple] = useState<CoupleOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [photoWarning, setPhotoWarning] = useState<string | null>(null);
  const [patientPhoto, setPatientPhoto] = useState<File | null>(null);
  const [partnerPhoto, setPartnerPhoto] = useState<File | null>(null);
  const [patientSignature, setPatientSignature] = useState<File | null>(null);
  const [partnerSignature, setPartnerSignature] = useState<File | null>(null);
  const [signatureWarning, setSignatureWarning] = useState<string | null>(null);
  const createCouple = useCreateCouple();

  const [form, setForm] = useState({
    name: '',
    dob: '',
    phone: '',
    email: '',
    address: '',
    blood: 'B Positive',
    nationality: 'Indian',
    isInternational: false,
    emergency: '',
    referral: '',
    pName: '',
    pDob: '',
    pPhone: '',
    pOccupation: '',
    pBlood: 'O Positive',
    infType: 'Primary Infertility',
    duration: '',
    pregnancies: '0',
    iui: '0',
    ivf: '0',
    history: '',
  });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const setBool = (k: 'isInternational', v: boolean) => setForm((f) => ({ ...f, [k]: v }));

  const create = () => {
    setError(null);
    createCouple.mutate(
      {
        female_patient: {
          full_name: form.name,
          date_of_birth: form.dob || null,
          gender: 'female',
          blood_group: form.blood,
          nationality: form.nationality || null,
          is_international: form.isInternational,
          phone: form.phone || null,
          email: form.email || null,
          address: form.address || null,
          emergency_contact: form.emergency || null,
          referral_source: form.referral || null,
        },
        male_patient: {
          full_name: form.pName,
          date_of_birth: form.pDob || null,
          gender: 'male',
          blood_group: form.pBlood,
          phone: form.pPhone || null,
          occupation: form.pOccupation || null,
        },
        infertility_type: form.infType,
        infertility_duration: form.duration || null,
        previous_iui_cycles: Number(form.iui) || 0,
        previous_ivf_cycles: Number(form.ivf) || 0,
        previous_treatment_notes: form.history || null,
      },
      {
        onSuccess: async (couple) => {
          setCreatedCouple(couple);

          // Attach each photo to its own person. The couple already exists at
          // this point, so a photo failure is surfaced as a non-fatal warning
          // (retry from the profile) rather than losing the registration.
          const failed: string[] = [];
          if (patientPhoto) {
            try {
              await uploadPatientDocument(couple.female_patient.id, 'photo', patientPhoto);
            } catch {
              failed.push('patient');
            }
          }
          if (partnerPhoto) {
            try {
              await uploadPatientDocument(couple.male_patient.id, 'photo', partnerPhoto);
            } catch {
              failed.push('partner');
            }
          }
          setPhotoWarning(
            failed.length
              ? `The couple was created, but the ${failed.join(' and ')} photo${failed.length > 1 ? 's' : ''} could not be uploaded. You can add ${failed.length > 1 ? 'them' : 'it'} from the patient profile.`
              : null,
          );

          // Same deferred-upload shape as the photos above: signatures are
          // drawn against local File state during the wizard (there is no
          // patient_id to upload against yet) and only actually persisted
          // once the couple record exists.
          const sigFailed: string[] = [];
          if (patientSignature) {
            try {
              await uploadPatientDocument(couple.female_patient.id, 'consent_signature', patientSignature);
            } catch {
              sigFailed.push('patient');
            }
          }
          if (partnerSignature) {
            try {
              await uploadPatientDocument(couple.male_patient.id, 'consent_signature', partnerSignature);
            } catch {
              sigFailed.push('partner');
            }
          }
          setSignatureWarning(
            sigFailed.length
              ? `The couple was created, but the ${sigFailed.join(' and ')} signature${sigFailed.length > 1 ? 's' : ''} could not be saved. Capture ${sigFailed.length > 1 ? 'them' : 'it'} again from the patient profile.`
              : null,
          );

          setDone(true);
          toast({
            title: 'Couple created successfully',
            body: `${couple.female_patient.full_name} and ${couple.male_patient.full_name} are now linked as a treatment case.`,
            tone: 'success',
          });
        },
        onError: (err) => {
          setError(err instanceof ApiError ? err.message : 'Could not create the couple. Please try again.');
        },
      }
    );
  };

  if (done) {
    return (
      <div className="screen-enter mx-auto flex max-w-[720px] flex-col items-center p-6 py-20 text-center lg:p-8">
        <div className="relative flex h-24 w-24 items-center justify-center">
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-brand-400/30" />
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-brand-400/20" style={{ animationDelay: '0.9s' }} />
          <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
            <Check className="h-10 w-10 text-white" strokeWidth={2.5} />
          </div>
        </div>

        <h2 className="tracking-display font-display mt-8 text-[32px] text-ink-900">
          Couple created successfully
        </h2>
        <p className="mt-2 text-[14px] text-ink-500">
          Both profiles are linked as a single treatment case and are ready for consultation.
        </p>

        <Card className="mt-8 w-full p-5">
          <div className="flex items-center justify-center gap-5">
            <div className="text-center">
              <Avatar initials={initialsOf(form.name)} size="lg" gradient="from-brand-500 to-teal-600" className="mx-auto" />
              <p className="mt-2 text-[14.5px] font-semibold text-ink-900">{form.name}</p>
              <p className="tnum text-[12.5px] text-ink-500">{createdCouple?.female_patient.uhid}</p>
            </div>

            <div className="flex flex-col items-center">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 ring-1 ring-brand-200">
                <Link2 className="h-4 w-4 text-brand-600" />
              </div>
              <p className="mt-1 text-[11.5px] font-medium uppercase tracking-wider text-brand-700">
                Linked
              </p>
            </div>

            <div className="text-center">
              <Avatar initials={initialsOf(form.pName)} size="lg" gradient="from-sky-500 to-blue-600" className="mx-auto" />
              <p className="mt-2 text-[14.5px] font-semibold text-ink-900">{form.pName}</p>
              <p className="tnum text-[12.5px] text-ink-500">{createdCouple?.male_patient.uhid}</p>
            </div>
          </div>
        </Card>

        {(photoWarning || signatureWarning) && (
          <div className="mt-5 flex w-full items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-left">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <p className="text-[13.5px] leading-relaxed text-amber-800">{[photoWarning, signatureWarning].filter(Boolean).join(' ')}</p>
          </div>
        )}

        {createdCouple && (
          <Card className="mt-5 w-full p-5 text-left">
            <MandatoryDocumentUpload
              patientId={createdCouple.female_patient.id}
              patientName={form.name}
              isInternational={form.isInternational}
            />
          </Card>
        )}

        <div className="mt-6 flex gap-3">
          <Button onClick={() => { setDone(false); setCreatedCouple(null); setStep(0); setPatientPhoto(null); setPartnerPhoto(null); setPhotoWarning(null); setPatientSignature(null); setPartnerSignature(null); setSignatureWarning(null); }}>Register another couple</Button>
          <Button
            variant="primary"
            iconRight={<ChevronRight className="h-4 w-4" />}
            onClick={() => createdCouple && openPatient(createdCouple.female_patient.id)}
          >
            Start Consultation
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="screen-enter mx-auto max-w-[1000px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SectionTitle
        eyebrow="Front Office"
        title="Patient & Couple Registration"
        description="Create linked profiles for both partners as a single treatment case"
      />

      {/* ============ STEPPER ============ */}
      <Card className="p-5">
        <div className="relative">
          <div className="absolute left-0 right-0 top-[19px] h-[2px] bg-ink-200" />
          <div
            className="absolute left-0 top-[19px] h-[2px] bg-gradient-to-r from-brand-500 to-brand-600 transition-[width] duration-600 ease-spring"
            style={{ width: `${(step / (STEPS.length - 1)) * 100}%` }}
          />
          <div className="relative flex justify-between">
            {STEPS.map((s) => {
              const Icon = s.icon;
              const done = step > s.id;
              const active = step === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => setStep(s.id)}
                  className="flex flex-1 flex-col items-center"
                >
                  <div
                    className={cn(
                      'relative z-10 flex h-10 w-10 items-center justify-center rounded-full ring-4 ring-white transition-all duration-300',
                      done ? 'bg-brand-600' : active ? 'bg-brand-600 shadow-glow' : 'border-2 border-ink-200 bg-white'
                    )}
                  >
                    {done ? (
                      <Check className="h-5 w-5 text-white" strokeWidth={3} />
                    ) : (
                      <Icon className={cn('h-4 w-4', active ? 'text-white' : 'text-ink-400')} />
                    )}
                  </div>
                  <p
                    className={cn(
                      'mt-2 hidden text-center text-[13px] font-medium sm:block',
                      active ? 'text-brand-800' : done ? 'text-ink-700' : 'text-ink-400'
                    )}
                  >
                    {s.label}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {/* ============ FORM ============ */}
      <Card>
        <CardHeader
          title={STEPS[step].label}
          subtitle={
            [
              'Primary patient demographic and contact information',
              'Partner profile — created as a full patient record, not a text field',
              'Fertility background used to shape the treatment plan',
              'Upload identification, reports and capture consent',
              'Confirm details before creating the linked treatment case',
            ][step]
          }
          icon={React.createElement(STEPS[step].icon, { className: 'h-4 w-4' })}
        />

        <div className="px-5 pb-5">
          {step === 0 && (
            <div className="animate-fade-up grid gap-4 sm:grid-cols-2">
              <Input label="Full Name" value={form.name} onChange={(e) => set('name', e.target.value)} />
              <Input
                label="Date of Birth"
                type="date"
                value={form.dob}
                onChange={(e) => set('dob', e.target.value)}
                hint={form.dob ? `Age ${ageFromDOB(form.dob)} years` : undefined}
              />
              <Input label="Mobile Number" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
              <Input label="Email Address" value={form.email} onChange={(e) => set('email', e.target.value)} />
              <Select label="Blood Group" value={form.blood} onChange={(e) => set('blood', e.target.value)}>
                {['A Positive', 'B Positive', 'O Positive', 'AB Positive', 'A Negative', 'B Negative', 'O Negative', 'AB Negative'].map((b) => (
                  <option key={b}>{b}</option>
                ))}
              </Select>
              <Input label="Referral Source" value={form.referral} onChange={(e) => set('referral', e.target.value)} />
              <Input label="Nationality" value={form.nationality} onChange={(e) => set('nationality', e.target.value)} />
              <label className="flex items-center gap-2.5 self-end pb-2.5">
                <input
                  type="checkbox"
                  checked={form.isInternational}
                  onChange={(e) => setBool('isInternational', e.target.checked)}
                  className="h-4 w-4 rounded border-ink-300 text-brand-600"
                />
                <span className="text-[13.5px] text-ink-700">International patient (requires visa, not Aadhaar)</span>
              </label>
              <div className="sm:col-span-2">
                <Input label="Address" value={form.address} onChange={(e) => set('address', e.target.value)} />
              </div>
              <div className="sm:col-span-2">
                <Input label="Emergency Contact" value={form.emergency} onChange={(e) => set('emergency', e.target.value)} />
              </div>
              <div className="sm:col-span-2">
                <PhotoCapture
                  idPrefix="patient"
                  label="Patient Photo"
                  value={patientPhoto}
                  onChange={setPatientPhoto}
                />
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="animate-fade-up space-y-4">
              <InfoNote tone="brand" icon={<Link2 className="h-4 w-4" />}>
                In fertility care you treat couples, not individuals. The partner is created as a
                complete patient record and linked to this treatment case.
              </InfoNote>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Full Name" value={form.pName} onChange={(e) => set('pName', e.target.value)} />
                <Input
                  label="Date of Birth"
                  type="date"
                  value={form.pDob}
                  onChange={(e) => set('pDob', e.target.value)}
                  hint={form.pDob ? `Age ${ageFromDOB(form.pDob)} years` : undefined}
                />
                <Input label="Mobile Number" value={form.pPhone} onChange={(e) => set('pPhone', e.target.value)} />
                <Input label="Occupation" value={form.pOccupation} onChange={(e) => set('pOccupation', e.target.value)} />
                <Select label="Blood Group" value={form.pBlood} onChange={(e) => set('pBlood', e.target.value)}>
                  {['O Positive', 'A Positive', 'B Positive', 'AB Positive'].map((b) => (
                    <option key={b}>{b}</option>
                  ))}
                </Select>
                <Select label="Relationship" defaultValue="Married — 6 Years">
                  <option>Married — 6 Years</option>
                  <option>Married — Other</option>
                  <option>Partner</option>
                </Select>
                <div className="sm:col-span-2">
                  <PhotoCapture
                    idPrefix="partner"
                    label="Partner Photo"
                    value={partnerPhoto}
                    onChange={setPartnerPhoto}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-fade-up grid gap-4 sm:grid-cols-2">
              <Select label="Infertility Type" value={form.infType} onChange={(e) => set('infType', e.target.value)}>
                <option>Primary Infertility</option>
                <option>Secondary Infertility</option>
              </Select>
              <Input label="Duration of Infertility" value={form.duration} onChange={(e) => set('duration', e.target.value)} />
              <Input label="Previous Pregnancies" value={form.pregnancies} onChange={(e) => set('pregnancies', e.target.value)} />
              <Input label="Previous IUI Cycles" value={form.iui} onChange={(e) => set('iui', e.target.value)} />
              <Input label="Previous IVF Cycles" value={form.ivf} onChange={(e) => set('ivf', e.target.value)} />
              <Select label="Referred For" defaultValue="IVF Evaluation">
                <option>IVF Evaluation</option>
                <option>IUI</option>
                <option>Fertility Assessment</option>
              </Select>
              <div className="sm:col-span-2">
                <label className="block">
                  <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">
                    Previous Treatment History
                  </span>
                  <textarea
                    rows={4}
                    value={form.history}
                    onChange={(e) => set('history', e.target.value)}
                    className="w-full resize-none rounded-lg border border-ink-200 bg-white p-3 text-[14.5px] text-ink-900"
                  />
                </label>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="animate-fade-up space-y-3">
              {[
                { l: 'Government photo identification', s: 'Aadhaar / Passport for both partners', done: true },
                { l: 'Marriage certificate', s: 'Required for treatment consent', done: true },
                { l: 'Previous treatment records', s: 'IUI cycle summaries from previous centre', done: true },
                { l: 'Data privacy acknowledgement', s: 'Patient information handling consent', done: false },
              ].map((d, i) => (
                <div
                  key={d.l}
                  className={cn(
                    'animate-fade-up flex items-center gap-3 rounded-xl border p-3.5',
                    d.done ? 'border-brand-200 bg-brand-50/50' : 'border-ink-200/70 bg-white'
                  )}
                  style={{ animationDelay: `${i * 70}ms` }}
                >
                  <div
                    className={cn(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                      d.done ? 'bg-brand-600' : 'border-2 border-dashed border-ink-300'
                    )}
                  >
                    {d.done && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-medium text-ink-900">{d.l}</p>
                    <p className="text-[12.5px] text-ink-500">{d.s}</p>
                  </div>
                  <Badge tone={d.done ? 'completed' : 'pending'} size="sm">
                    {d.done ? 'Received' : 'Pending'}
                  </Badge>
                </div>
              ))}

              <div className="animate-fade-up rounded-xl border border-ink-200/70 bg-white p-3.5" style={{ animationDelay: '280ms' }}>
                <div className="mb-3 flex items-center gap-3">
                  <div
                    className={cn(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                      patientSignature && partnerSignature ? 'bg-brand-600' : 'border-2 border-dashed border-ink-300'
                    )}
                  >
                    {patientSignature && partnerSignature && <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-medium text-ink-900">General treatment consent</p>
                    <p className="text-[12.5px] text-ink-500">Signed on this device — finger, stylus or Apple Pencil</p>
                  </div>
                  <Badge tone={patientSignature && partnerSignature ? 'completed' : 'pending'} size="sm">
                    {patientSignature && partnerSignature ? 'Received' : 'Pending'}
                  </Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <SignatureCapture
                    idPrefix="patient-consent"
                    label={`${form.name || 'Patient'} — signature`}
                    value={patientSignature}
                    onChange={setPatientSignature}
                  />
                  <SignatureCapture
                    idPrefix="partner-consent"
                    label={`${form.pName || 'Partner'} — signature`}
                    value={partnerSignature}
                    onChange={setPartnerSignature}
                  />
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="animate-fade-up space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Card className="p-4">
                  <div className="mb-3 flex items-center gap-2.5">
                    <ReviewPhoto file={patientPhoto} initials={initialsOf(form.name)} gradient="from-brand-500 to-teal-600" />
                    <div>
                      <p className="text-[14.5px] font-semibold text-ink-900">{form.name || 'Patient'}</p>
                      <p className="text-[12.5px] text-brand-700">UHID assigned on creation</p>
                    </div>
                  </div>
                  <Field label="Date of Birth" value={form.dob ? new Date(form.dob).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }) : '—'} />
                  <div className="mt-2.5"><Field label="Blood Group" value={form.blood} /></div>
                  <div className="mt-2.5"><Field label="Mobile" value={form.phone || '—'} /></div>
                </Card>

                <Card className="p-4">
                  <div className="mb-3 flex items-center gap-2.5">
                    <ReviewPhoto file={partnerPhoto} initials={initialsOf(form.pName)} gradient="from-sky-500 to-blue-600" />
                    <div>
                      <p className="text-[14.5px] font-semibold text-ink-900">{form.pName || 'Partner'}</p>
                      <p className="text-[12.5px] text-sky-700">UHID assigned on creation</p>
                    </div>
                  </div>
                  <Field label="Date of Birth" value={form.pDob ? new Date(form.pDob).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }) : '—'} />
                  <div className="mt-2.5"><Field label="Blood Group" value={form.pBlood} /></div>
                  <div className="mt-2.5"><Field label="Occupation" value={form.pOccupation || '—'} /></div>
                </Card>
              </div>

              <Card className="p-4">
                <p className="mb-3 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-500">
                  Fertility Summary
                </p>
                <div className="grid gap-4 sm:grid-cols-4">
                  <Field label="Type" value={form.infType} />
                  <Field label="Duration" value={form.duration} />
                  <Field label="Previous IUI" value={`${form.iui} cycles`} />
                  <Field label="Previous IVF" value={`${form.ivf} cycles`} />
                </div>
              </Card>

              <InfoNote tone="brand" icon={<ShieldCheck className="h-4 w-4" />}>
                Both profiles will be created and permanently linked as a treatment couple. All
                subsequent clinical records, cycles and billing will be associated with this case.
              </InfoNote>
            </div>
          )}
        </div>

        {step === 4 && error && (
          <div className="mx-5 mb-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
          </div>
        )}

        {/* ============ NAV ============ */}
        <div className="flex items-center justify-between border-t border-ink-100 bg-ink-50/50 px-5 py-4">
          <Button
            icon={<ChevronLeft className="h-4 w-4" />}
            disabled={step === 0}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
          >
            Back
          </Button>

          <span className="tnum text-[13px] text-ink-400">
            Step {step + 1} of {STEPS.length}
          </span>

          {step < STEPS.length - 1 ? (
            <Button variant="primary" iconRight={<ChevronRight className="h-4 w-4" />} onClick={() => setStep((s) => s + 1)}>
              Continue
            </Button>
          ) : (
            <Button
              variant="primary"
              loading={createCouple.isPending}
              icon={<Sparkles className="h-4 w-4" />}
              disabled={!form.name || !form.pName || createCouple.isPending}
              onClick={create}
            >
              {createCouple.isPending ? 'Creating…' : 'Create Couple & Start Consultation'}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
