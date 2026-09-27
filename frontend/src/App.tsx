import { Route, Routes } from 'react-router-dom'

import Landing from './pages/Landing.jsx'
import EmergencyCountdown from './pages/patient/EmergencyCountdown.jsx'

import PatientLayout from './layouts/PatientLayout.jsx'
import HospitalLayout from './layouts/HospitalLayout.jsx'
import AdminLayout from './layouts/AdminLayout.jsx'

import PatientHome from './pages/patient/PatientHome.jsx'
import PatientAssessment from './pages/patient/PatientAssessment.jsx'
import PatientHospitalOptions from './pages/patient/PatientHospitalOptions.jsx'
import PatientJourneyTracking from './pages/patient/PatientJourneyTracking.jsx'
import PatientReferral from './pages/patient/PatientReferral.jsx'
import EmergencyStatus from './pages/patient/EmergencyStatus.jsx'

import HospitalDashboard from './pages/hospital/HospitalDashboard.jsx'
import ReferralDetail from './pages/hospital/ReferralDetail.jsx'

import NetworkOverview from './pages/admin/NetworkOverview.jsx'
import Simulator from './pages/admin/Simulator.jsx'
import LiveEvents from './pages/admin/LiveEvents.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />

      <Route path="/patient" element={<PatientLayout />}>
        <Route index element={<PatientHome />} />
        <Route path="assessment" element={<PatientAssessment />} />
        <Route path="options" element={<PatientHospitalOptions />} />
        <Route path="journey" element={<PatientJourneyTracking />} />
        <Route path="referral" element={<PatientReferral />} />
        <Route path="emergency-countdown" element={<EmergencyCountdown />} />
        <Route path="emergency-status" element={<EmergencyStatus />} />
      </Route>

      <Route path="/hospital" element={<HospitalLayout />}>
        <Route index element={<HospitalDashboard />} />
        <Route path="referral/:referralId" element={<ReferralDetail />} />
      </Route>

      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<NetworkOverview />} />
        <Route path="network" element={<NetworkOverview />} />
        <Route path="simulator" element={<Simulator />} />
        <Route path="events" element={<LiveEvents />} />
      </Route>
    </Routes>
  )
}
