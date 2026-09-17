// ============================================================
// CLINICAL DATA LAYER
// Mirrors the shape of the future REST API so screens can be
// re-pointed at live endpoints without refactoring.
// ============================================================

export type Role = 'doctor' | 'receptionist' | 'embryologist' | 'management' | 'pharmacist';

export type StatusTone =
  | 'active'
  | 'completed'
  | 'pending'
  | 'attention'
  | 'critical'
  | 'scheduled'
  | 'cancelled'
  | 'neutral';

export interface StaffUser {
  id: string;
  role: Role;
  name: string;
  title: string;
  initials: string;
  email: string;
  department: string;
  accent: string;
}

export const USERS: Record<Role, StaffUser> = {
  doctor: {
    id: 'DAIVF-STAFF-001',
    role: 'doctor',
    name: 'Dr. Archana S. Ayyanathan',
    title: 'Chief Consultant & IVF Specialist',
    initials: 'AA',
    email: 'archana@drarchanaivf.in',
    department: 'Reproductive Medicine',
    accent: 'from-emerald-500 to-teal-600',
  },
  receptionist: {
    id: 'DAIVF-STAFF-014',
    role: 'receptionist',
    name: 'Lakshmi Narayanan',
    title: 'Front Office Executive',
    initials: 'LN',
    email: 'lakshmi@drarchanaivf.in',
    department: 'Patient Services',
    accent: 'from-sky-500 to-blue-600',
  },
  embryologist: {
    id: 'DAIVF-STAFF-007',
    role: 'embryologist',
    name: 'Dr. Meera Kapoor',
    title: 'Senior Clinical Embryologist',
    initials: 'MK',
    email: 'meera@drarchanaivf.in',
    department: 'Embryology Laboratory',
    accent: 'from-violet-500 to-purple-600',
  },
  management: {
    id: 'DAIVF-STAFF-002',
    role: 'management',
    name: 'Rajesh Venkatesan',
    title: 'Hospital Administrator',
    initials: 'RV',
    email: 'rajesh@drarchanaivf.in',
    department: 'Operations & Finance',
    accent: 'from-amber-500 to-orange-600',
  },
  pharmacist: {
    id: 'DAIVF-STAFF-015',
    role: 'pharmacist',
    name: 'Ganesh Prabhu',
    title: 'Pharmacist-in-Charge',
    initials: 'GP',
    email: 'ganesh@drarchanaivf.in',
    department: 'Pharmacy',
    accent: 'from-rose-500 to-pink-600',
  },
};

// ------------------------------------------------------------
// PRIMARY DEMO COUPLE
// ------------------------------------------------------------

export const PATIENT = {
  id: 'DAIVF-2026-00428',
  name: 'Priya Raman',
  initials: 'PR',
  age: 31,
  dob: '18 September 1994',
  bloodGroup: 'B Positive',
  phone: '+91 98407 21894',
  email: 'priya.raman@gmail.com',
  address: 'T-4, Anandam Apartments, Alwarpet, Chennai 600018',
  occupation: 'Architect',
  emergencyContact: 'Arjun Kumar (Spouse) — +91 98410 33127',
  referralSource: 'Referred by Dr. Sudha Menon, Apollo Chennai',
  allergies: 'No known drug allergies',
  infertilityType: 'Primary Infertility',
  duration: '6 Years',
  previousIUI: 2,
  previousIVF: 0,
  amh: '2.4 ng/mL',
  afc: '14 (7 right / 7 left)',
  bmi: '23.4',
  protocol: 'GnRH Antagonist Protocol',
  treatment: 'IVF with ICSI',
  cycleId: 'IVF-2026-00428',
  cycleDay: 8,
  phase: 'Ovarian Stimulation',
  registeredOn: '2 July 2026',
  consultant: 'Dr. Archana S. Ayyanathan',
};

export const PARTNER = {
  id: 'DAIVF-2026-00429',
  name: 'Arjun Kumar',
  initials: 'AK',
  age: 34,
  dob: '22 May 1992',
  bloodGroup: 'O Positive',
  phone: '+91 98410 33127',
  email: 'arjun.kumar@gmail.com',
  occupation: 'Senior Software Engineer',
  relationship: 'Married — 6 Years',
  semenAnalysis: {
    volume: '3.2 mL',
    concentration: '18 million/mL',
    motility: '38% progressive',
    morphology: '3% normal forms',
    verdict: 'Mild oligoasthenoteratozoospermia — ICSI advised',
  },
};

// ------------------------------------------------------------
// PATIENT REGISTRY
// ------------------------------------------------------------

export interface PatientRow {
  id: string;
  name: string;
  initials: string;
  age: number;
  partner: string;
  stage: string;
  tone: StatusTone;
  cycleDay: string;
  consultant: string;
  lastVisit: string;
  amh: string;
}

export const PATIENTS: PatientRow[] = [
  {
    id: 'DAIVF-2026-00428',
    name: 'Priya Raman',
    initials: 'PR',
    age: 31,
    partner: 'Arjun Kumar',
    stage: 'Ovarian Stimulation',
    tone: 'active',
    cycleDay: 'Day 8',
    consultant: 'Dr. Archana',
    lastVisit: 'Today, 9:30 AM',
    amh: '2.4',
  },
  {
    id: 'DAIVF-2026-00391',
    name: 'Nandhini Selvaraj',
    initials: 'NS',
    age: 29,
    partner: 'Rahul Menon',
    stage: 'Embryo Transfer',
    tone: 'scheduled',
    cycleDay: 'Transfer Day',
    consultant: 'Dr. Archana',
    lastVisit: 'Today, 11:30 AM',
    amh: '3.1',
  },
  {
    id: 'DAIVF-2026-00364',
    name: 'Kavitha Ramesh',
    initials: 'KR',
    age: 34,
    partner: 'Ramesh Iyer',
    stage: 'Fertility Assessment',
    tone: 'pending',
    cycleDay: '—',
    consultant: 'Dr. Archana',
    lastVisit: 'Today, 10:00 AM',
    amh: '1.8',
  },
  {
    id: 'DAIVF-2026-00312',
    name: 'Meera Sundaram',
    initials: 'MS',
    age: 32,
    partner: 'Vignesh Kumar',
    stage: 'Pregnancy Follow-up',
    tone: 'completed',
    cycleDay: '7 Weeks',
    consultant: 'Dr. Archana',
    lastVisit: 'Today, 2:00 PM',
    amh: '2.9',
  },
  {
    id: 'DAIVF-2026-00298',
    name: 'Divya Prakash',
    initials: 'DP',
    age: 36,
    partner: 'Prakash Nair',
    stage: 'Embryology',
    tone: 'active',
    cycleDay: 'Day 3 Culture',
    consultant: 'Dr. Archana',
    lastVisit: '28 July 2026',
    amh: '1.2',
  },
  {
    id: 'DAIVF-2026-00276',
    name: 'Anitha Balaji',
    initials: 'AB',
    age: 28,
    partner: 'Balaji Srinivasan',
    stage: 'Oocyte Retrieval',
    tone: 'scheduled',
    cycleDay: 'Trigger Given',
    consultant: 'Dr. Archana',
    lastVisit: '28 July 2026',
    amh: '4.2',
  },
  {
    id: 'DAIVF-2026-00241',
    name: 'Shalini Venkat',
    initials: 'SV',
    age: 38,
    partner: 'Venkat Raman',
    stage: 'Ovarian Stimulation',
    tone: 'attention',
    cycleDay: 'Day 10',
    consultant: 'Dr. Archana',
    lastVisit: '29 July 2026',
    amh: '0.9',
  },
  {
    id: 'DAIVF-2026-00205',
    name: 'Revathi Krishnan',
    initials: 'RK',
    age: 30,
    partner: 'Krishnan Iyer',
    stage: 'Cryo Transfer Planning',
    tone: 'pending',
    cycleDay: '—',
    consultant: 'Dr. Archana',
    lastVisit: '26 July 2026',
    amh: '2.6',
  },
];

// ------------------------------------------------------------
// TODAY'S SCHEDULE
// ------------------------------------------------------------

export interface Appointment {
  id: string;
  time: string;
  patient: string;
  patientId?: string;
  initials: string;
  visit: string;
  status: string;
  tone: StatusTone;
  room: string;
}

export const APPOINTMENTS: Appointment[] = [
  {
    id: 'APT-2026-1841',
    time: '09:30',
    patient: 'Priya Raman & Arjun Kumar',
    patientId: 'DAIVF-2026-00428',
    initials: 'PR',
    visit: 'Follicle Monitoring — Day 8',
    status: 'Waiting',
    tone: 'attention',
    room: 'Scan Room 2',
  },
  {
    id: 'APT-2026-1842',
    time: '10:00',
    patient: 'Kavitha Ramesh',
    patientId: 'DAIVF-2026-00364',
    initials: 'KR',
    visit: 'IVF Consultation',
    status: 'Confirmed',
    tone: 'scheduled',
    room: 'Consult 1',
  },
  {
    id: 'APT-2026-1843',
    time: '10:45',
    patient: 'Shalini Venkat',
    patientId: 'DAIVF-2026-00241',
    initials: 'SV',
    visit: 'Monitoring — Poor Responder Review',
    status: 'In Progress',
    tone: 'active',
    room: 'Scan Room 1',
  },
  {
    id: 'APT-2026-1844',
    time: '11:30',
    patient: 'Nandhini Selvaraj & Rahul Menon',
    patientId: 'DAIVF-2026-00391',
    initials: 'NS',
    visit: 'Embryo Transfer',
    status: 'Scheduled',
    tone: 'scheduled',
    room: 'OT — Transfer Suite',
  },
  {
    id: 'APT-2026-1845',
    time: '14:00',
    patient: 'Meera Sundaram',
    patientId: 'DAIVF-2026-00312',
    initials: 'MS',
    visit: 'Pregnancy Follow-up — 7 Weeks',
    status: 'Confirmed',
    tone: 'scheduled',
    room: 'Consult 1',
  },
  {
    id: 'APT-2026-1846',
    time: '15:30',
    patient: 'Anitha Balaji',
    patientId: 'DAIVF-2026-00276',
    initials: 'AB',
    visit: 'Pre-Retrieval Counselling',
    status: 'Confirmed',
    tone: 'scheduled',
    room: 'Consult 2',
  },
];

// ------------------------------------------------------------
// DASHBOARD METRICS
// ------------------------------------------------------------

export const METRICS = {
  appointments: { value: 24, label: 'Appointments Today', delta: '+3 vs yesterday', trend: [16, 19, 17, 22, 20, 24, 24] },
  waiting: { value: 7, label: 'Patients Waiting', delta: 'Avg wait 12 min', trend: [3, 5, 4, 6, 8, 7, 7] },
  cycles: { value: 12, label: 'Active IVF Cycles', delta: '+2 this week', trend: [8, 9, 9, 10, 11, 12, 12] },
  collection: { value: 184000, label: "Today's Collection", delta: '+18% vs avg', trend: [120, 142, 131, 158, 166, 172, 184] },
  procedures: { value: 3, label: 'Procedures Scheduled', delta: '1 retrieval, 2 transfers', trend: [2, 3, 1, 4, 2, 3, 3] },
  followups: { value: 8, label: 'Follow-ups Due', delta: '3 pregnancy reviews', trend: [5, 6, 7, 6, 9, 8, 8] },
};

export const CLINICAL_ALERTS = [
  {
    id: 'AL-1',
    title: 'Monitoring reports awaiting review',
    detail: 'Priya Raman (Day 8) and Shalini Venkat (Day 10) require doctor sign-off.',
    count: 2,
    tone: 'attention' as StatusTone,
    action: 'Review Now',
  },
  {
    id: 'AL-2',
    title: 'Trigger timing confirmation required',
    detail: 'Anitha Balaji — lead follicle 19 mm, trigger decision due today.',
    count: 1,
    tone: 'critical' as StatusTone,
    action: 'Confirm Trigger',
  },
  {
    id: 'AL-3',
    title: 'Pregnancy follow-ups due today',
    detail: 'Meera Sundaram, Deepa Rajan and Sowmya Iyer scheduled for beta-hCG review.',
    count: 3,
    tone: 'scheduled' as StatusTone,
    action: 'Open List',
  },
  {
    id: 'AL-4',
    title: 'Cryostorage renewals approaching',
    detail: '2 storage consents expire within 30 days — patient consent renewal required.',
    count: 2,
    tone: 'pending' as StatusTone,
    action: 'View Storage',
  },
];

export const ACTIVITY_FEED = [
  { id: 'A1', actor: 'Dr. Meera Kapoor', action: "uploaded Day 8 monitoring for Priya Raman", time: '12 minutes ago', kind: 'lab' },
  { id: 'A2', actor: 'Embryology Lab', action: 'moved Embryo E-02 to cryostorage Tank A / Canister 04', time: '38 minutes ago', kind: 'embryo' },
  { id: 'A3', actor: 'Lakshmi Narayanan', action: "recorded ₹75,000 package payment from Kavitha Ramesh", time: '1 hour ago', kind: 'billing' },
  { id: 'A4', actor: 'Dr. Archana', action: 'finalised treatment plan for Anitha Balaji', time: '2 hours ago', kind: 'clinical' },
  { id: 'A5', actor: 'Lakshmi Narayanan', action: 'registered new couple — Revathi & Krishnan', time: '3 hours ago', kind: 'registration' },
  { id: 'A6', actor: 'Dr. Archana', action: 'updated Gonal-F dosage for Shalini Venkat', time: '4 hours ago', kind: 'clinical' },
];

// Active cycle distribution across pipeline stages
export const CYCLE_DISTRIBUTION = [
  { stage: 'Assessment', count: 3, color: '#94A3B8' },
  { stage: 'Stimulation', count: 4, color: '#10B981' },
  { stage: 'Retrieval', count: 1, color: '#F59E0B' },
  { stage: 'Embryology', count: 2, color: '#8B5CF6' },
  { stage: 'Transfer', count: 1, color: '#0EA5E9' },
  { stage: 'Follow-up', count: 1, color: '#EC4899' },
];

// ------------------------------------------------------------
// IVF JOURNEY TIMELINE
// ------------------------------------------------------------

export interface TimelineStage {
  id: string;
  title: string;
  date: string;
  status: 'completed' | 'active' | 'upcoming';
  summary: string;
  details: { label: string; value: string }[];
  link?: string;
}

export const TIMELINE: TimelineStage[] = [
  {
    id: 'ts-1',
    title: 'Initial Consultation',
    date: '4 July 2026',
    status: 'completed',
    summary: 'Comprehensive fertility assessment completed for both partners.',
    details: [
      { label: 'Consultant', value: 'Dr. Archana S. Ayyanathan' },
      { label: 'Diagnosis', value: 'Primary infertility — 6 years' },
      { label: 'History', value: '2 previous IUI cycles, both unsuccessful' },
      { label: 'Outcome', value: 'Advised IVF with ICSI' },
    ],
  },
  {
    id: 'ts-2',
    title: 'Diagnostic Investigations',
    date: '6 – 10 July 2026',
    status: 'completed',
    summary: 'Baseline hormonal profile, pelvic ultrasound and semen analysis completed.',
    details: [
      { label: 'AMH', value: '2.4 ng/mL — normal ovarian reserve' },
      { label: 'Antral Follicle Count', value: '14 (7 right / 7 left)' },
      { label: 'Semen Analysis', value: 'Mild OAT — ICSI indicated' },
      { label: 'Hysteroscopy', value: 'Normal uterine cavity' },
    ],
    link: 'investigations',
  },
  {
    id: 'ts-3',
    title: 'Treatment Plan Finalised',
    date: '12 July 2026',
    status: 'completed',
    summary: 'GnRH antagonist protocol selected. Consent and package activated.',
    details: [
      { label: 'Protocol', value: 'GnRH Antagonist' },
      { label: 'Stimulation', value: 'Gonal-F 225 IU daily' },
      { label: 'Package', value: 'Complete IVF Treatment — ₹2,50,000' },
      { label: 'Consent', value: 'Signed and verified' },
    ],
    link: 'plan',
  },
  {
    id: 'ts-4',
    title: 'Ovarian Stimulation',
    date: 'Started 22 July 2026 — Currently Day 8',
    status: 'active',
    summary: 'Follicular response progressing appropriately. Monitoring every 48 hours.',
    details: [
      { label: 'Current Day', value: 'Stimulation Day 8' },
      { label: 'Lead Follicle', value: '17 mm (right ovary)' },
      { label: 'Endometrium', value: '8.2 mm — trilaminar' },
      { label: 'Next Review', value: '30 July 2026' },
    ],
    link: 'monitoring',
  },
  {
    id: 'ts-5',
    title: 'Trigger Injection',
    date: 'Planned — 31 July 2026',
    status: 'upcoming',
    summary: 'hCG trigger once lead follicles reach 18–20 mm.',
    details: [
      { label: 'Planned Agent', value: 'Ovitrelle 250 mcg' },
      { label: 'Timing', value: '35 hours before retrieval' },
      { label: 'Criteria', value: '≥3 follicles at 17 mm+' },
    ],
  },
  {
    id: 'ts-6',
    title: 'Oocyte Retrieval',
    date: 'Expected — 2 August 2026',
    status: 'upcoming',
    summary: 'Transvaginal ultrasound-guided oocyte aspiration under sedation.',
    details: [
      { label: 'Procedure', value: 'TVOR under short GA' },
      { label: 'Expected Yield', value: '12 – 16 oocytes' },
      { label: 'Anaesthetist', value: 'Dr. Sanjay Rao' },
    ],
  },
  {
    id: 'ts-7',
    title: 'Embryology & Culture',
    date: 'Expected — 2 – 7 August 2026',
    status: 'upcoming',
    summary: 'ICSI fertilisation followed by extended blastocyst culture to Day 5.',
    details: [
      { label: 'Method', value: 'ICSI' },
      { label: 'Culture', value: 'Continuous time-lapse to Day 5' },
      { label: 'Embryologist', value: 'Dr. Meera Kapoor' },
    ],
    link: 'embryology',
  },
  {
    id: 'ts-8',
    title: 'Embryo Transfer',
    date: 'Expected — 7 August 2026',
    status: 'upcoming',
    summary: 'Single blastocyst transfer under ultrasound guidance.',
    details: [
      { label: 'Plan', value: 'Elective single embryo transfer' },
      { label: 'Support', value: 'Luteal phase progesterone' },
    ],
    link: 'transfer',
  },
  {
    id: 'ts-9',
    title: 'Pregnancy Follow-up',
    date: 'From 21 August 2026',
    status: 'upcoming',
    summary: 'Beta-hCG at Day 14, followed by serial ultrasound milestones.',
    details: [
      { label: 'First Test', value: 'Beta-hCG — Day 14 post transfer' },
      { label: 'First Scan', value: '6 weeks gestation' },
    ],
    link: 'pregnancy',
  },
];

// ------------------------------------------------------------
// STIMULATION MONITORING
// ------------------------------------------------------------

export interface MonitoringVisit {
  day: number;
  date: string;
  right: number[];
  left: number[];
  endometrium: number;
  estradiol: number;
  lh: number;
  progesterone: number;
  note: string;
  reviewed: boolean;
}

export const MONITORING_HISTORY: MonitoringVisit[] = [
  {
    day: 2,
    date: '23 July 2026',
    right: [6, 5, 5, 4],
    left: [6, 5, 4, 4],
    endometrium: 4.1,
    estradiol: 186,
    lh: 3.1,
    progesterone: 0.3,
    note: 'Baseline scan satisfactory. No residual cysts. Commence Gonal-F 225 IU.',
    reviewed: true,
  },
  {
    day: 5,
    date: '26 July 2026',
    right: [11, 10, 9, 8],
    left: [10, 9, 8, 7],
    endometrium: 6.4,
    estradiol: 642,
    lh: 4.2,
    progesterone: 0.5,
    note: 'Even cohort recruitment. Continue current dosage. Add Cetrotide from Day 6.',
    reviewed: true,
  },
  {
    day: 8,
    date: '29 July 2026',
    right: [17, 15, 14, 12],
    left: [16, 15, 13, 11],
    endometrium: 8.2,
    estradiol: 1420,
    lh: 4.8,
    progesterone: 0.7,
    note: 'Follicular response is progressing appropriately. Continue the current dosage and repeat monitoring tomorrow.',
    reviewed: false,
  },
];

export const MEDICATIONS = [
  { name: 'Gonal-F', dose: '225 IU', route: 'Subcutaneous — daily', status: 'Active', since: 'Day 1', tone: 'active' as StatusTone },
  { name: 'Cetrotide', dose: '0.25 mg', route: 'Subcutaneous — daily', status: 'Active', since: 'Day 6', tone: 'active' as StatusTone },
  { name: 'Folic Acid', dose: '5 mg', route: 'Oral — daily', status: 'Ongoing', since: 'Pre-cycle', tone: 'completed' as StatusTone },
  { name: 'Ovitrelle', dose: '250 mcg', route: 'Subcutaneous — single', status: 'Planned', since: 'Day 10', tone: 'pending' as StatusTone },
];

export const HORMONE_REFERENCE = [
  { key: 'estradiol', label: 'Estradiol (E2)', unit: 'pg/mL', value: 1420, range: '1,000 – 2,000', status: 'Optimal', tone: 'completed' as StatusTone },
  { key: 'lh', label: 'Luteinising Hormone', unit: 'mIU/mL', value: 4.8, range: '< 10', status: 'Suppressed', tone: 'completed' as StatusTone },
  { key: 'progesterone', label: 'Progesterone', unit: 'ng/mL', value: 0.7, range: '< 1.5', status: 'Normal', tone: 'completed' as StatusTone },
];

// ------------------------------------------------------------
// EMBRYOLOGY
// ------------------------------------------------------------

export const EMBRYO_SUMMARY = [
  { label: 'Oocytes Retrieved', value: 14, sub: 'TVOR — 2 Aug 2026' },
  { label: 'Mature Oocytes', value: 11, sub: 'MII stage' },
  { label: 'Normally Fertilised', value: 8, sub: '2PN — 73% rate' },
  { label: 'Day 3 Embryos', value: 7, sub: 'Cleavage stage' },
  { label: 'Blastocysts', value: 5, sub: 'Day 5 / Day 6' },
];

export interface Embryo {
  id: string;
  day: number;
  grade: string;
  expansion: string;
  icm: string;
  trophectoderm: string;
  status: string;
  tone: StatusTone;
  note: string;
  storage?: string;
  frozen?: string;
  score: number;
}

export const EMBRYOS: Embryo[] = [
  {
    id: 'E-01',
    day: 5,
    grade: '4AA',
    expansion: 'Expanded blastocyst',
    icm: 'A — tightly packed, many cells',
    trophectoderm: 'A — cohesive epithelium',
    status: 'Selected for Transfer',
    tone: 'active',
    note: 'Top quality blastocyst. Even expansion, no fragmentation. Recommended for fresh transfer.',
    score: 96,
  },
  {
    id: 'E-02',
    day: 5,
    grade: '4AB',
    expansion: 'Expanded blastocyst',
    icm: 'A — prominent inner cell mass',
    trophectoderm: 'B — few larger cells',
    status: 'Cryopreserved',
    tone: 'completed',
    note: 'Excellent morphology. Vitrified on Day 5 for future frozen transfer.',
    storage: 'Tank A / Canister 04 / Cane 02 / Goblet 05 / Straw 03',
    frozen: '4 August 2026',
    score: 88,
  },
  {
    id: 'E-03',
    day: 6,
    grade: '3BB',
    expansion: 'Full blastocyst',
    icm: 'B — loosely grouped cells',
    trophectoderm: 'B — moderate cell number',
    status: 'Cryopreserved',
    tone: 'completed',
    note: 'Good quality Day 6 blastocyst. Delayed expansion but viable.',
    storage: 'Tank A / Canister 04 / Cane 02 / Goblet 05 / Straw 04',
    frozen: '5 August 2026',
    score: 74,
  },
  {
    id: 'E-04',
    day: 5,
    grade: '3BC',
    expansion: 'Full blastocyst',
    icm: 'B — moderate quality',
    trophectoderm: 'C — sparse, irregular cells',
    status: 'Under Clinical Review',
    tone: 'attention',
    note: 'Fair quality. Trophectoderm grading borderline. Awaiting embryologist and clinician joint review.',
    score: 58,
  },
  {
    id: 'E-05',
    day: 6,
    grade: '3CC',
    expansion: 'Full blastocyst',
    icm: 'C — few cells',
    trophectoderm: 'C — sparse cells',
    status: 'Not Suitable for Transfer',
    tone: 'cancelled',
    note: 'Poor morphology on Day 6. Discussed with couple — not recommended for cryopreservation.',
    score: 31,
  },
];

export const CRYO_HIERARCHY = {
  tank: 'Tank A',
  canister: 'Canister 04',
  cane: 'Cane 02',
  goblet: 'Goblet 05',
  straws: [
    { id: 'Straw 03', embryo: 'E-02', grade: '4AB', frozen: '4 Aug 2026', status: 'Active' },
    { id: 'Straw 04', embryo: 'E-03', grade: '3BB', frozen: '5 Aug 2026', status: 'Active' },
  ],
  temperature: '-196 °C',
  consent: 'Verified — signed 3 Aug 2026',
  renewal: '4 August 2027',
  custody: [
    { at: '4 Aug 2026, 11:42', by: 'Dr. Meera Kapoor', event: 'Vitrification completed — E-02 loaded to Straw 03' },
    { at: '4 Aug 2026, 11:58', by: 'Dr. Meera Kapoor', event: 'Straw transferred to Tank A / Canister 04 / Cane 02' },
    { at: '4 Aug 2026, 12:05', by: 'Anand Kumar (Lab Tech)', event: 'Witness verification completed — double signature recorded' },
    { at: '5 Aug 2026, 10:20', by: 'Dr. Meera Kapoor', event: 'E-03 vitrified and stored in Straw 04' },
    { at: '5 Aug 2026, 18:00', by: 'System', event: 'Automated tank temperature log — -196 °C, nominal' },
  ],
};

export const TRANSFER_CHECKLIST = [
  { id: 'c1', label: 'Patient identity verified', detail: 'Priya Raman — DAIVF-2026-00428 — verified against photo ID and wristband' },
  { id: 'c2', label: 'Couple information verified', detail: 'Arjun Kumar — DAIVF-2026-00429 — partner consent on file' },
  { id: 'c3', label: 'Embryo identity verified', detail: 'E-01 — Day 5 — Grade 4AA — dish label double-witnessed' },
  { id: 'c4', label: 'Consent confirmed', detail: 'Embryo transfer consent signed 6 Aug 2026 by both partners' },
  { id: 'c5', label: 'Clinical team verified', detail: 'Dr. Archana S. Ayyanathan (Clinician), Dr. Meera Kapoor (Embryologist)' },
  { id: 'c6', label: 'Procedure documentation completed', detail: 'Catheter batch, media lot and witness signatures recorded' },
];

// ------------------------------------------------------------
// PREGNANCY
// ------------------------------------------------------------

export const BETA_HCG = [
  { day: 'Day 14', value: 612, verdict: 'Positive', tone: 'completed' as StatusTone },
  { day: 'Day 16', value: 1248, verdict: 'Appropriate rise', tone: 'completed' as StatusTone },
  { day: 'Day 21', value: 5840, verdict: 'Strong progression', tone: 'completed' as StatusTone },
];

export const PREGNANCY_MILESTONES = [
  { label: 'Embryo Transfer', date: '7 Aug 2026', status: 'completed' as const, detail: 'Single blastocyst E-01 transferred' },
  { label: 'Positive Beta-hCG', date: '21 Aug 2026', status: 'completed' as const, detail: '612 mIU/mL — biochemical pregnancy confirmed' },
  { label: 'Gestational Sac', date: '4 Sep 2026', status: 'completed' as const, detail: '6 weeks — single intrauterine sac visualised' },
  { label: 'Cardiac Activity', date: '11 Sep 2026', status: 'completed' as const, detail: '7 weeks — fetal heart rate 128 bpm' },
  { label: 'First Trimester Scan', date: '9 Oct 2026', status: 'upcoming' as const, detail: '11–13 weeks NT scan scheduled' },
  { label: 'Delivery Outcome', date: 'May 2027', status: 'upcoming' as const, detail: 'Estimated due date 15 May 2027' },
];

// ------------------------------------------------------------
// BILLING
// ------------------------------------------------------------

export const PACKAGE = {
  name: 'Complete IVF Treatment Package',
  value: 250000,
  paid: 175000,
  outstanding: 75000,
  inclusions: [
    { item: 'Consultations (unlimited)', status: 'Included' },
    { item: 'Stimulation monitoring scans', status: 'Included' },
    { item: 'Oocyte retrieval & anaesthesia', status: 'Included' },
    { item: 'ICSI & embryology laboratory', status: 'Included' },
    { item: 'Embryo transfer procedure', status: 'Included' },
    { item: 'Stimulation medicines', status: 'Excluded' },
    { item: 'Additional investigations', status: 'Excluded' },
    { item: 'Cryostorage (per year)', status: 'Additional' },
  ],
};

export const INVOICES = [
  { id: 'INV-2026-0912', date: '12 July 2026', description: 'IVF Package — Advance (40%)', amount: 100000, method: 'Bank Transfer', status: 'Paid' },
  { id: 'INV-2026-1043', date: '22 July 2026', description: 'IVF Package — Second instalment (30%)', amount: 75000, method: 'UPI — HDFC', status: 'Paid' },
  { id: 'INV-2026-1188', date: '2 August 2026', description: 'IVF Package — Final instalment (30%)', amount: 75000, method: '—', status: 'Due' },
  { id: 'INV-2026-1201', date: '4 August 2026', description: 'Cryostorage — 1 year (2 straws)', amount: 18000, method: '—', status: 'Due' },
];

// ------------------------------------------------------------
// MANAGEMENT ANALYTICS
// ------------------------------------------------------------

export const REVENUE_TREND = [
  { month: 'Feb', revenue: 38.2, cycles: 14 },
  { month: 'Mar', revenue: 42.6, cycles: 17 },
  { month: 'Apr', revenue: 39.8, cycles: 15 },
  { month: 'May', revenue: 47.1, cycles: 19 },
  { month: 'Jun', revenue: 52.4, cycles: 22 },
  { month: 'Jul', revenue: 58.9, cycles: 26 },
];

export const MANAGEMENT_KPIS = [
  { label: 'New Patients This Month', value: 38, delta: '+22%', positive: true },
  { label: 'Active IVF Cycles', value: 12, delta: '+2', positive: true },
  { label: 'Embryo Transfers', value: 19, delta: '+4', positive: true },
  { label: 'Clinical Pregnancy Rate', value: 62, suffix: '%', delta: '+5 pts', positive: true },
];

export const OUTCOME_BREAKDOWN = [
  { label: 'Clinical Pregnancy', value: 62, color: '#10B981' },
  { label: 'Biochemical Only', value: 11, color: '#F59E0B' },
  { label: 'Not Pregnant', value: 27, color: '#D6D3D1' },
];

export const OPERATIONAL_METRICS = [
  { label: 'Monthly Revenue', value: '₹58.9 L', delta: '+12.4%', positive: true },
  { label: 'Daily Collection', value: '₹1.84 L', delta: '+18%', positive: true },
  { label: 'Outstanding Payments', value: '₹9.2 L', delta: '-6.1%', positive: true },
  { label: 'Appointment Volume', value: '486', delta: '+9%', positive: true },
  { label: 'Pharmacy Sales', value: '₹7.4 L', delta: '+3.2%', positive: true },
  { label: 'Inventory Alerts', value: '4', delta: '2 critical', positive: false },
];

export const DOCTOR_PERFORMANCE = [
  { name: 'Dr. Archana S. Ayyanathan', consultations: 186, cycles: 24, transfers: 12, success: 66 },
  { name: 'Dr. Kavya Raghunathan', consultations: 142, cycles: 15, transfers: 8, success: 61 },
  { name: 'Dr. Suresh Ramachandran', consultations: 118, cycles: 11, transfers: 6, success: 58 },
];

// ------------------------------------------------------------
// ROLE PERMISSIONS
// ------------------------------------------------------------

export const ROLE_MATRIX: Record<Role, { allowed: string[]; restricted: string[]; summary: string }> = {
  doctor: {
    summary: 'Full clinical authority across patient care, treatment planning and cycle management.',
    allowed: ['Complete Patient Profile', 'Clinical Notes', 'Treatment Plans', 'IVF Cycle Management', 'Follicle Monitoring', 'Prescriptions', 'Embryology Review', 'Procedure Sign-off'],
    restricted: ['Accounting Configuration', 'Payroll & Staff Salary'],
  },
  receptionist: {
    summary: 'Front-office operations — registration, scheduling, queue and basic billing.',
    allowed: ['Patient Registration', 'Appointment Scheduling', 'Queue Management', 'Basic Billing & Receipts', 'Document Upload'],
    restricted: ['Embryology Details', 'Detailed Clinical Notes', 'Management Reports', 'Treatment Plans'],
  },
  embryologist: {
    summary: 'Laboratory workspace covering oocytes, embryo development, grading and cryostorage.',
    allowed: ['IVF Cycle Information', 'Oocyte Assessment', 'Embryo Development & Grading', 'Cryostorage Management', 'Chain of Custody', 'Lab Witness Sign-off'],
    restricted: ['Financial Reports', 'Accounting', 'Patient Billing', 'Staff Administration'],
  },
  management: {
    summary: 'Operational and financial oversight with configurable clinical visibility.',
    allowed: ['Hospital Dashboard', 'Operational Reports', 'Revenue & Collections', 'Clinical Performance Metrics', 'Inventory Insights', 'Audit Logs'],
    restricted: ['Individual Clinical Notes', 'Embryo-level Laboratory Data'],
  },
  pharmacist: {
    summary: 'Pharmacy operations — medicine catalogue, vendors, purchases, stock and dispensing.',
    allowed: ['Medicine Catalogue', 'Vendor Management', 'Purchase Entry & GRN', 'Stock & Batch Tracking', 'Stock Adjustment', 'Dispensing & Sales Returns'],
    restricted: ['Clinical Notes', 'Treatment Plans', 'Financial Reports', 'Staff Administration'],
  },
};

// ------------------------------------------------------------
// AUDIT LOG
// ------------------------------------------------------------

export const AUDIT_LOG = [
  { id: 'AU-8841', user: 'Dr. Archana S. Ayyanathan', action: 'Medication updated', entity: 'IVF-2026-00428 — Gonal-F 225 IU', time: '29 Jul 2026, 09:48', ip: '10.0.4.22', tone: 'active' as StatusTone },
  { id: 'AU-8840', user: 'Dr. Meera Kapoor', action: 'Monitoring record created', entity: 'IVF-2026-00428 — Day 8 scan', time: '29 Jul 2026, 09:31', ip: '10.0.4.18', tone: 'completed' as StatusTone },
  { id: 'AU-8839', user: 'Lakshmi Narayanan', action: 'Payment recorded', entity: 'INV-2026-1043 — ₹75,000', time: '29 Jul 2026, 08:55', ip: '10.0.4.09', tone: 'completed' as StatusTone },
  { id: 'AU-8838', user: 'Dr. Meera Kapoor', action: 'Cryostorage transfer', entity: 'E-02 → Tank A / Canister 04', time: '28 Jul 2026, 17:12', ip: '10.0.4.18', tone: 'scheduled' as StatusTone },
  { id: 'AU-8837', user: 'Rajesh Venkatesan', action: 'Report exported', entity: 'July operational summary', time: '28 Jul 2026, 16:40', ip: '10.0.4.31', tone: 'neutral' as StatusTone },
  { id: 'AU-8836', user: 'System', action: 'Failed login attempt blocked', entity: 'Unknown device — Chennai', time: '28 Jul 2026, 02:14', ip: '49.37.x.x', tone: 'critical' as StatusTone },
];

export const NOTIFICATIONS = [
  { id: 'N1', title: 'Day 8 monitoring awaiting your review', body: 'Priya Raman — uploaded 12 minutes ago by Dr. Meera Kapoor.', time: '12m', unread: true, tone: 'attention' as StatusTone },
  { id: 'N2', title: 'Trigger decision required', body: 'Anitha Balaji — lead follicle 19 mm. Confirm trigger timing today.', time: '45m', unread: true, tone: 'critical' as StatusTone },
  { id: 'N3', title: 'Embryo E-02 cryopreserved', body: 'Vitrification complete. Witness verification recorded.', time: '2h', unread: true, tone: 'completed' as StatusTone },
  { id: 'N4', title: 'Package payment received', body: 'Kavitha Ramesh — ₹75,000 via UPI.', time: '3h', unread: false, tone: 'completed' as StatusTone },
  { id: 'N5', title: 'Cryostorage consent expiring', body: '2 storage consents expire within 30 days.', time: '1d', unread: false, tone: 'pending' as StatusTone },
];

export const INVESTIGATIONS = [
  { name: 'Anti-Müllerian Hormone (AMH)', value: '2.4 ng/mL', ref: '1.0 – 4.0', date: '6 Jul 2026', flag: 'normal' as const },
  { name: 'Follicle Stimulating Hormone', value: '6.8 mIU/mL', ref: '3.5 – 12.5', date: '6 Jul 2026', flag: 'normal' as const },
  { name: 'Thyroid Stimulating Hormone', value: '2.1 µIU/mL', ref: '0.4 – 4.0', date: '6 Jul 2026', flag: 'normal' as const },
  { name: 'Prolactin', value: '18.4 ng/mL', ref: '4.8 – 23.3', date: '6 Jul 2026', flag: 'normal' as const },
  { name: 'Vitamin D (25-OH)', value: '18 ng/mL', ref: '30 – 100', date: '6 Jul 2026', flag: 'low' as const },
  { name: 'Antral Follicle Count', value: '14', ref: '10 – 20', date: '8 Jul 2026', flag: 'normal' as const },
  { name: 'Semen Analysis (Partner)', value: '18 M/mL, 38% motile', ref: '≥16 M/mL, ≥30%', date: '9 Jul 2026', flag: 'low' as const },
  { name: 'Hysteroscopy', value: 'Normal cavity', ref: 'Normal', date: '10 Jul 2026', flag: 'normal' as const },
];

export const CONSULTATIONS = [
  { date: '4 Jul 2026', type: 'Initial Fertility Consultation', doctor: 'Dr. Archana', note: 'Couple with 6 years primary infertility. Two failed IUI cycles. Advised complete workup and likely IVF-ICSI.' },
  { date: '12 Jul 2026', type: 'Treatment Planning', doctor: 'Dr. Archana', note: 'Reviewed investigations. AMH 2.4, AFC 14. Partner sample shows mild OAT. Plan: antagonist protocol with ICSI. Counselled on success rates and risks.' },
  { date: '22 Jul 2026', type: 'Cycle Initiation', doctor: 'Dr. Archana', note: 'Baseline scan clear. Commenced Gonal-F 225 IU. Injection technique demonstrated. Review Day 5.' },
  { date: '26 Jul 2026', type: 'Monitoring Review — Day 5', doctor: 'Dr. Archana', note: 'Good even cohort. E2 rising appropriately. Continue dose, start Cetrotide Day 6.' },
];

// ------------------------------------------------------------
// APPOINTMENT MANAGEMENT — full booking, queue, calendar
// ------------------------------------------------------------

export const DOCTORS = [
  { id: 'DOC-01', name: 'Dr. Archana S. Ayyanathan', specialty: 'Chief Consultant & IVF Specialist', color: '#059669', todayCount: 8 },
  { id: 'DOC-02', name: 'Dr. Kavya Raghunathan', specialty: 'IVF Consultant', color: '#0EA5E9', todayCount: 6 },
  { id: 'DOC-03', name: 'Dr. Suresh Ramachandran', specialty: 'Andrologist', color: '#8B5CF6', todayCount: 4 },
];

export interface BookingSlot {
  id: string;
  time: string;
  doctorId: string;
  patient: string;
  patientId?: string;
  initials: string;
  type: string;
  channel: 'Walk-in' | 'Online' | 'Phone';
  status: 'Waiting' | 'Confirmed' | 'In Progress' | 'Completed' | 'Cancelled' | 'No Show';
  tone: StatusTone;
}

export const APPOINTMENT_BOOK: BookingSlot[] = [
  { id: 'BK-01', time: '09:00', doctorId: 'DOC-01', patient: 'Priya Raman & Arjun Kumar', patientId: 'DAIVF-2026-00428', initials: 'PR', type: 'Follicle Monitoring', channel: 'Online', status: 'Waiting', tone: 'attention' },
  { id: 'BK-02', time: '09:30', doctorId: 'DOC-02', patient: 'Divya Prakash', patientId: 'DAIVF-2026-00298', initials: 'DP', type: 'Embryology Review', channel: 'Phone', status: 'Confirmed', tone: 'scheduled' },
  { id: 'BK-03', time: '10:00', doctorId: 'DOC-01', patient: 'Kavitha Ramesh', patientId: 'DAIVF-2026-00364', initials: 'KR', type: 'IVF Consultation', channel: 'Walk-in', status: 'Confirmed', tone: 'scheduled' },
  { id: 'BK-04', time: '10:45', doctorId: 'DOC-01', patient: 'Shalini Venkat', patientId: 'DAIVF-2026-00241', initials: 'SV', type: 'Monitoring Review', channel: 'Online', status: 'In Progress', tone: 'active' },
  { id: 'BK-05', time: '11:00', doctorId: 'DOC-03', patient: 'Balaji Srinivasan', initials: 'BS', type: 'Semen Analysis Review', channel: 'Walk-in', status: 'Waiting', tone: 'attention' },
  { id: 'BK-06', time: '11:30', doctorId: 'DOC-01', patient: 'Nandhini Selvaraj & Rahul Menon', patientId: 'DAIVF-2026-00391', initials: 'NS', type: 'Embryo Transfer', channel: 'Online', status: 'Confirmed', tone: 'scheduled' },
  { id: 'BK-07', time: '12:15', doctorId: 'DOC-02', patient: 'Revathi Krishnan', patientId: 'DAIVF-2026-00205', initials: 'RK', type: 'Cryo Transfer Planning', channel: 'Phone', status: 'Confirmed', tone: 'scheduled' },
  { id: 'BK-08', time: '14:00', doctorId: 'DOC-01', patient: 'Meera Sundaram', patientId: 'DAIVF-2026-00312', initials: 'MS', type: 'Pregnancy Follow-up', channel: 'Online', status: 'Confirmed', tone: 'scheduled' },
  { id: 'BK-09', time: '15:30', doctorId: 'DOC-01', patient: 'Anitha Balaji', patientId: 'DAIVF-2026-00276', initials: 'AB', type: 'Pre-Retrieval Counselling', channel: 'Walk-in', status: 'Confirmed', tone: 'scheduled' },
  { id: 'BK-10', time: '16:00', doctorId: 'DOC-03', patient: 'Prakash Nair', initials: 'PN', type: 'Fertility Consultation', channel: 'Online', status: 'Cancelled', tone: 'cancelled' },
  { id: 'BK-11', time: '09:15', doctorId: 'DOC-02', patient: 'Lavanya Subramaniam', initials: 'LS', type: 'Follow-up Consultation', channel: 'Phone', status: 'No Show', tone: 'critical' },
  { id: 'BK-12', time: 'Yesterday', doctorId: 'DOC-01', patient: 'Vignesh Kumar', initials: 'VK', type: 'IVF Consultation', channel: 'Walk-in', status: 'Completed', tone: 'completed' },
];

export const APPOINTMENT_METRICS = {
  totalToday: 24,
  confirmed: 17,
  waiting: 3,
  cancelled: 2,
  noShow: 1,
  onlineBookings: 14,
};

// ------------------------------------------------------------
// LABORATORY MANAGEMENT — test ordering, sample tracking
// ------------------------------------------------------------

export interface LabOrder {
  id: string;
  patient: string;
  patientId?: string;
  test: string;
  orderedBy: string;
  orderedOn: string;
  sampleType: string;
  source: 'Internal Lab' | 'External Lab';
  externalLab?: string;
  status: 'Ordered' | 'Sample Collected' | 'In Progress' | 'Report Ready' | 'Delivered';
  tone: StatusTone;
  priority: 'Routine' | 'Urgent';
}

export const LAB_ORDERS: LabOrder[] = [
  { id: 'LAB-3391', patient: 'Priya Raman', patientId: 'DAIVF-2026-00428', test: 'Estradiol (E2), LH, Progesterone', orderedBy: 'Dr. Archana', orderedOn: '29 Jul 2026, 08:10', sampleType: 'Venous Blood', source: 'Internal Lab', status: 'Report Ready', tone: 'completed', priority: 'Urgent' },
  { id: 'LAB-3390', patient: 'Shalini Venkat', patientId: 'DAIVF-2026-00241', test: 'Estradiol (E2), LH', orderedBy: 'Dr. Archana', orderedOn: '29 Jul 2026, 08:05', sampleType: 'Venous Blood', source: 'Internal Lab', status: 'In Progress', tone: 'active', priority: 'Urgent' },
  { id: 'LAB-3389', patient: 'Kavitha Ramesh', patientId: 'DAIVF-2026-00364', test: 'AMH, FSH, TSH, Prolactin', orderedBy: 'Dr. Archana', orderedOn: '29 Jul 2026, 07:40', sampleType: 'Venous Blood', source: 'External Lab', externalLab: 'Neuberg Diagnostics, Chennai', status: 'Sample Collected', tone: 'scheduled', priority: 'Routine' },
  { id: 'LAB-3388', patient: 'Balaji Srinivasan', test: 'Semen Analysis (Advanced)', orderedBy: 'Dr. Suresh Ramachandran', orderedOn: '28 Jul 2026, 16:20', sampleType: 'Semen', source: 'Internal Lab', status: 'Report Ready', tone: 'completed', priority: 'Routine' },
  { id: 'LAB-3387', patient: 'Meera Sundaram', patientId: 'DAIVF-2026-00312', test: 'Beta-hCG (Quantitative)', orderedBy: 'Dr. Archana', orderedOn: '28 Jul 2026, 14:00', sampleType: 'Venous Blood', source: 'Internal Lab', status: 'Delivered', tone: 'completed', priority: 'Urgent' },
  { id: 'LAB-3386', patient: 'Revathi Krishnan', patientId: 'DAIVF-2026-00205', test: 'Thyroid Panel, Vitamin D', orderedBy: 'Dr. Kavya Raghunathan', orderedOn: '28 Jul 2026, 11:15', sampleType: 'Venous Blood', source: 'External Lab', externalLab: 'Metropolis Healthcare', status: 'Ordered', tone: 'pending', priority: 'Routine' },
  { id: 'LAB-3385', patient: 'Divya Prakash', patientId: 'DAIVF-2026-00298', test: 'Karyotyping', orderedBy: 'Dr. Kavya Raghunathan', orderedOn: '27 Jul 2026, 10:00', sampleType: 'Venous Blood', source: 'External Lab', externalLab: 'Neuberg Diagnostics, Chennai', status: 'In Progress', tone: 'active', priority: 'Routine' },
];

export const LAB_METRICS = {
  ordersToday: 7,
  awaitingCollection: 1,
  inProgress: 2,
  reportsReady: 2,
  externalPending: 2,
};

// ------------------------------------------------------------
// PHARMACY MANAGEMENT
// ------------------------------------------------------------

export interface PharmacyItem {
  id: string;
  name: string;
  category: string;
  batch: string;
  expiry: string;
  stock: number;
  reorderLevel: number;
  unit: string;
  mrp: number;
  supplier: string;
  gst: number;
}

export const PHARMACY_ITEMS: PharmacyItem[] = [
  { id: 'MED-001', name: 'Gonal-F 225 IU Injection', category: 'Gonadotropin', batch: 'GNF-2607', expiry: 'Mar 2027', stock: 42, reorderLevel: 20, unit: 'Pen', mrp: 3450, supplier: 'Merck Serono India', gst: 12 },
  { id: 'MED-002', name: 'Cetrotide 0.25mg Injection', category: 'GnRH Antagonist', batch: 'CTR-1182', expiry: 'Jan 2027', stock: 18, reorderLevel: 20, unit: 'Vial', mrp: 1280, supplier: 'Merck Serono India', gst: 12 },
  { id: 'MED-003', name: 'Ovitrelle 250mcg Injection', category: 'Trigger Agent', batch: 'OVT-0994', expiry: 'Nov 2026', stock: 9, reorderLevel: 15, unit: 'Pen', mrp: 2150, supplier: 'Merck Serono India', gst: 12 },
  { id: 'MED-004', name: 'Progesterone 400mg Pessary', category: 'Luteal Support', batch: 'PRG-3341', expiry: 'Jun 2027', stock: 210, reorderLevel: 100, unit: 'Strip', mrp: 480, supplier: 'Cadila Pharmaceuticals', gst: 12 },
  { id: 'MED-005', name: 'Folic Acid 5mg Tablet', category: 'Supplement', batch: 'FA-7712', expiry: 'Sep 2027', stock: 340, reorderLevel: 150, unit: 'Strip', mrp: 45, supplier: 'Mankind Pharma', gst: 5 },
  { id: 'MED-006', name: 'Gonal-F 900 IU Multidose', category: 'Gonadotropin', batch: 'GNF-2588', expiry: 'Feb 2027', stock: 6, reorderLevel: 10, unit: 'Pen', mrp: 11200, supplier: 'Merck Serono India', gst: 12 },
  { id: 'MED-007', name: 'Duphaston 10mg Tablet', category: 'Luteal Support', batch: 'DUP-4471', expiry: 'Aug 2027', stock: 128, reorderLevel: 80, unit: 'Strip', mrp: 220, supplier: 'Abbott India', gst: 12 },
  { id: 'MED-008', name: 'HCG 5000IU Injection', category: 'Trigger Agent', batch: 'HCG-2201', expiry: 'Dec 2026', stock: 14, reorderLevel: 15, unit: 'Vial', mrp: 890, supplier: 'Bharat Serums', gst: 12 },
];

export const PHARMACY_SALES = [
  { id: 'RX-4471', patient: 'Priya Raman', date: '29 Jul 2026, 09:52', items: 'Gonal-F 225 IU × 3, Folic Acid × 1', amount: 10395, status: 'Dispensed', tone: 'completed' as StatusTone },
  { id: 'RX-4470', patient: 'Shalini Venkat', date: '29 Jul 2026, 09:15', items: 'Cetrotide 0.25mg × 4', amount: 5120, status: 'Dispensed', tone: 'completed' as StatusTone },
  { id: 'RX-4469', patient: 'Meera Sundaram', date: '28 Jul 2026, 14:30', items: 'Duphaston 10mg × 2, Folic Acid × 2', amount: 530, status: 'Dispensed', tone: 'completed' as StatusTone },
  { id: 'RX-4468', patient: 'Anitha Balaji', date: '28 Jul 2026, 11:05', items: 'Ovitrelle 250mcg × 1', amount: 2150, status: 'Pending Pickup', tone: 'pending' as StatusTone },
];

export const PHARMACY_METRICS = {
  todaySales: 15515,
  itemsBelowReorder: 3,
  expiringWithin90Days: 2,
  totalSKUs: PHARMACY_ITEMS.length,
};

// ------------------------------------------------------------
// INVENTORY MANAGEMENT — consumables, cryogenic supplies, equipment
// ------------------------------------------------------------

export interface InventoryItem {
  id: string;
  name: string;
  category: 'IVF Consumables' | 'Cryogenic Supplies' | 'Lab Supplies' | 'Surgical Equipment';
  stock: number;
  unit: string;
  reorderLevel: number;
  location: string;
  supplier: string;
  lastRestocked: string;
  status: 'In Stock' | 'Low Stock' | 'Critical' | 'On Order';
  tone: StatusTone;
}

export const INVENTORY_ITEMS: InventoryItem[] = [
  { id: 'INV-101', name: 'ICSI Micropipettes', category: 'IVF Consumables', stock: 84, unit: 'Pieces', reorderLevel: 50, location: 'Embryology Lab — Cabinet A', supplier: 'Cook Medical', lastRestocked: '18 Jul 2026', status: 'In Stock', tone: 'completed' },
  { id: 'INV-102', name: 'Embryo Culture Media (Sequential)', category: 'IVF Consumables', stock: 6, unit: 'Kits', reorderLevel: 10, location: 'Embryology Lab — Cold Storage', supplier: 'Vitrolife', lastRestocked: '10 Jul 2026', status: 'Low Stock', tone: 'attention' },
  { id: 'INV-103', name: 'Vitrification Straws', category: 'Cryogenic Supplies', stock: 145, unit: 'Pieces', reorderLevel: 100, location: 'Cryostorage Room', supplier: 'CryoBio Systems', lastRestocked: '22 Jul 2026', status: 'In Stock', tone: 'completed' },
  { id: 'INV-104', name: 'Liquid Nitrogen', category: 'Cryogenic Supplies', stock: 2, unit: 'Dewars (50L)', reorderLevel: 3, location: 'Cryostorage Room', supplier: 'Chennai Cryogenics', lastRestocked: '25 Jul 2026', status: 'Critical', tone: 'critical' },
  { id: 'INV-105', name: 'Oocyte Retrieval Needles', category: 'Surgical Equipment', stock: 22, unit: 'Pieces', reorderLevel: 15, location: 'OT — Store 2', supplier: 'Cook Medical', lastRestocked: '15 Jul 2026', status: 'In Stock', tone: 'completed' },
  { id: 'INV-106', name: 'Embryo Transfer Catheters', category: 'Surgical Equipment', stock: 11, unit: 'Pieces', reorderLevel: 15, location: 'OT — Store 2', supplier: 'Cook Medical', lastRestocked: '12 Jul 2026', status: 'Low Stock', tone: 'attention' },
  { id: 'INV-107', name: 'Sterile Petri Dishes', category: 'Lab Supplies', stock: 320, unit: 'Pieces', reorderLevel: 150, location: 'Embryology Lab — Cabinet B', supplier: 'Nunc / Thermo Fisher', lastRestocked: '20 Jul 2026', status: 'In Stock', tone: 'completed' },
  { id: 'INV-108', name: 'Ultrasound Gel', category: 'Lab Supplies', stock: 4, unit: 'Bottles (5L)', reorderLevel: 6, location: 'Scan Room 1 & 2', supplier: 'Sonogel India', lastRestocked: '8 Jul 2026', status: 'On Order', tone: 'scheduled' },
];

export const PURCHASE_ORDERS = [
  { id: 'PO-2291', item: 'Embryo Culture Media (Sequential)', supplier: 'Vitrolife', qty: 15, amount: 187500, status: 'Approved', date: '28 Jul 2026', tone: 'scheduled' as StatusTone },
  { id: 'PO-2290', item: 'Liquid Nitrogen', supplier: 'Chennai Cryogenics', qty: 5, amount: 42000, status: 'Pending Approval', date: '29 Jul 2026', tone: 'attention' as StatusTone },
  { id: 'PO-2289', item: 'Ultrasound Gel', supplier: 'Sonogel India', qty: 20, amount: 18000, status: 'Dispatched', date: '26 Jul 2026', tone: 'active' as StatusTone },
  { id: 'PO-2288', item: 'Embryo Transfer Catheters', supplier: 'Cook Medical', qty: 25, amount: 87500, status: 'Received', date: '20 Jul 2026', tone: 'completed' as StatusTone },
];

export const INVENTORY_METRICS = {
  totalItems: INVENTORY_ITEMS.length,
  lowStock: INVENTORY_ITEMS.filter((i) => i.status === 'Low Stock').length,
  critical: INVENTORY_ITEMS.filter((i) => i.status === 'Critical').length,
  onOrder: PURCHASE_ORDERS.filter((p) => p.status !== 'Received').length,
  stockValue: 1842000,
};

// ------------------------------------------------------------
// ACCOUNTING — cash book, ledger, GST, P&L
// ------------------------------------------------------------

export const CASH_BOOK = [
  { date: '29 Jul 2026', particulars: 'Package payment — Kavitha Ramesh', type: 'Receipt', mode: 'UPI', amount: 75000, balance: 1284500 },
  { date: '29 Jul 2026', particulars: 'Pharmacy purchase — Merck Serono', type: 'Payment', mode: 'Bank Transfer', amount: -112000, balance: 1209500 },
  { date: '28 Jul 2026', particulars: 'Consultation fees — 6 patients', type: 'Receipt', mode: 'Cash', amount: 9000, balance: 1321500 },
  { date: '28 Jul 2026', particulars: 'Staff salary — July (partial)', type: 'Payment', mode: 'Bank Transfer', amount: -420000, balance: 1312500 },
  { date: '27 Jul 2026', particulars: 'Package payment — Nandhini Selvaraj', type: 'Receipt', mode: 'Bank Transfer', amount: 100000, balance: 1732500 },
  { date: '26 Jul 2026', particulars: 'Equipment maintenance — Ultrasound', type: 'Payment', mode: 'Cheque', amount: -35000, balance: 1632500 },
];

export const GST_SUMMARY = {
  period: 'July 2026',
  outputGST: 284600,
  inputGST: 96200,
  netPayable: 188400,
  filingStatus: 'Draft — Due 20 Aug 2026',
};

export const PROFIT_LOSS = {
  period: 'July 2026 (Month to Date)',
  revenue: [
    { label: 'Consultation Fees', value: 412000 },
    { label: 'IVF Package Revenue', value: 4280000 },
    { label: 'Pharmacy Sales', value: 468000 },
    { label: 'Laboratory Charges', value: 186000 },
  ],
  expenses: [
    { label: 'Staff Salaries', value: 1850000 },
    { label: 'Medical Supplies & Pharmacy Purchases', value: 920000 },
    { label: 'Equipment & Maintenance', value: 210000 },
    { label: 'Utilities & Rent', value: 340000 },
    { label: 'Administrative Expenses', value: 128000 },
  ],
};

export const LEDGER_ACCOUNTS = [
  { name: 'Patient Receivables', debit: 920000, credit: 0, balance: 920000 },
  { name: 'Pharmacy Payable — Merck Serono', debit: 0, credit: 112000, balance: -112000 },
  { name: 'Bank Account — HDFC Current', debit: 5840000, credit: 4230000, balance: 1610000 },
  { name: 'Cash in Hand', debit: 186000, credit: 112000, balance: 74000 },
  { name: 'GST Payable', debit: 96200, credit: 284600, balance: -188400 },
];

// ------------------------------------------------------------
// STAFF MANAGEMENT
// ------------------------------------------------------------

export interface StaffMember {
  id: string;
  name: string;
  role: string;
  department: string;
  phone: string;
  joined: string;
  status: 'Present' | 'On Leave' | 'Absent';
  tone: StatusTone;
  leaveBalance: number;
}

export const STAFF_DIRECTORY: StaffMember[] = [
  { id: 'EMP-001', name: 'Dr. Archana S. Ayyanathan', role: 'Chief Consultant', department: 'Reproductive Medicine', phone: '+91 98400 11223', joined: '2 Jan 2014', status: 'Present', tone: 'completed', leaveBalance: 12 },
  { id: 'EMP-002', name: 'Dr. Kavya Raghunathan', role: 'IVF Consultant', department: 'Reproductive Medicine', phone: '+91 98400 22334', joined: '14 Mar 2020', status: 'Present', tone: 'completed', leaveBalance: 9 },
  { id: 'EMP-003', name: 'Dr. Meera Kapoor', role: 'Senior Embryologist', department: 'Embryology Laboratory', phone: '+91 98400 33445', joined: '5 Jun 2019', status: 'Present', tone: 'completed', leaveBalance: 14 },
  { id: 'EMP-004', name: 'Anand Kumar', role: 'Lab Technician', department: 'Embryology Laboratory', phone: '+91 98400 44556', joined: '20 Aug 2021', status: 'Present', tone: 'completed', leaveBalance: 8 },
  { id: 'EMP-005', name: 'Lakshmi Narayanan', role: 'Front Office Executive', department: 'Patient Services', phone: '+91 98400 55667', joined: '11 Nov 2022', status: 'Present', tone: 'completed', leaveBalance: 6 },
  { id: 'EMP-006', name: 'Divya Sundaresan', role: 'Staff Nurse', department: 'Nursing', phone: '+91 98400 66778', joined: '3 Feb 2021', status: 'On Leave', tone: 'attention', leaveBalance: 4 },
  { id: 'EMP-007', name: 'Ganesh Prabhu', role: 'Pharmacist', department: 'Pharmacy', phone: '+91 98400 77889', joined: '17 Sep 2020', status: 'Present', tone: 'completed', leaveBalance: 10 },
  { id: 'EMP-008', name: 'Rajesh Venkatesan', role: 'Hospital Administrator', department: 'Operations & Finance', phone: '+91 98400 88990', joined: '1 Jan 2014', status: 'Present', tone: 'completed', leaveBalance: 15 },
  { id: 'EMP-009', name: 'Swathi Ramesh', role: 'Accountant', department: 'Accounts', phone: '+91 98400 99001', joined: '8 Jul 2023', status: 'Absent', tone: 'critical', leaveBalance: 3 },
  { id: 'EMP-010', name: 'Karthik Balan', role: 'Store & Inventory Manager', department: 'Inventory', phone: '+91 98400 10112', joined: '25 Apr 2022', status: 'Present', tone: 'completed', leaveBalance: 7 },
];

export const LEAVE_REQUESTS = [
  { staff: 'Divya Sundaresan', type: 'Sick Leave', from: '28 Jul 2026', to: '30 Jul 2026', days: 3, status: 'Approved', tone: 'completed' as StatusTone },
  { staff: 'Swathi Ramesh', type: 'Casual Leave', from: '29 Jul 2026', to: '29 Jul 2026', days: 1, status: 'Pending', tone: 'attention' as StatusTone },
  { staff: 'Ganesh Prabhu', type: 'Annual Leave', from: '5 Aug 2026', to: '9 Aug 2026', days: 5, status: 'Pending', tone: 'attention' as StatusTone },
];

export const STAFF_METRICS = {
  totalStaff: STAFF_DIRECTORY.length,
  presentToday: STAFF_DIRECTORY.filter((s) => s.status === 'Present').length,
  onLeave: STAFF_DIRECTORY.filter((s) => s.status === 'On Leave').length,
  pendingLeaveRequests: LEAVE_REQUESTS.filter((l) => l.status === 'Pending').length,
};

// ------------------------------------------------------------
// SYSTEM ADMINISTRATION — master settings
// ------------------------------------------------------------

export const PROCEDURE_CHARGES = [
  { procedure: 'Initial IVF Consultation', charge: 1500 },
  { procedure: 'Follow-up Consultation', charge: 800 },
  { procedure: 'Follicle Monitoring Scan', charge: 1200 },
  { procedure: 'Oocyte Retrieval (TVOR)', charge: 45000 },
  { procedure: 'ICSI Procedure', charge: 35000 },
  { procedure: 'Embryo Transfer', charge: 25000 },
  { procedure: 'Embryo Vitrification (per batch)', charge: 15000 },
  { procedure: 'Cryostorage — Annual (per straw)', charge: 9000 },
];

export const TREATMENT_PACKAGES = [
  { name: 'Complete IVF Treatment Package', price: 250000, validity: '1 Cycle', inclusions: 8 },
  { name: 'IUI Package (3 Cycles)', price: 75000, validity: '6 Months', inclusions: 4 },
  { name: 'Frozen Embryo Transfer Package', price: 65000, validity: '1 Cycle', inclusions: 5 },
  { name: 'Fertility Assessment Package', price: 18000, validity: '30 Days', inclusions: 6 },
];

export const LAB_TEST_CATALOGUE = [
  { test: 'AMH (Anti-Müllerian Hormone)', price: 2200, tat: '24 hrs' },
  { test: 'FSH / LH Panel', price: 900, tat: '12 hrs' },
  { test: 'Estradiol (E2)', price: 750, tat: '6 hrs' },
  { test: 'Beta-hCG (Quantitative)', price: 650, tat: '4 hrs' },
  { test: 'Semen Analysis (Advanced)', price: 1500, tat: '24 hrs' },
  { test: 'Thyroid Profile (TSH, T3, T4)', price: 850, tat: '12 hrs' },
  { test: 'Karyotyping', price: 6500, tat: '10 days' },
];

export const SYSTEM_SETTINGS_GROUPS = [
  { group: 'Users & Roles', items: ['Staff accounts', 'Role permissions', 'Login policy'], icon: 'users' },
  { group: 'Clinical Master Data', items: ['Doctor profiles', 'Lab test catalogue', 'Treatment protocols'], icon: 'clipboard' },
  { group: 'Billing Configuration', items: ['Procedure charges', 'Treatment packages', 'GST & tax rates'], icon: 'receipt' },
  { group: 'Notifications', items: ['SMS templates', 'Email templates', 'WhatsApp integration'], icon: 'bell' },
  { group: 'Security', items: ['Two-factor authentication', 'Session timeout', 'IP / network restriction'], icon: 'shield' },
  { group: 'System', items: ['Backup schedule', 'Audit retention', 'Branding & identity'], icon: 'settings' },
];
