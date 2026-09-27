import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const client = axios.create({ baseURL: BASE_URL })

// Single place HTTP calls live, per section 41R ("do not scatter
// HTTP calls or model-loading code across React components").

export const api = {
  health: () => client.get('/health').then((r) => r.data),
  ready: () => client.get('/ready').then((r) => r.data),

  listHospitals: () => client.get('/hospitals').then((r) => r.data),
  getHospital: (id) => client.get(`/hospitals/${id}`).then((r) => r.data),
  getHospitalState: (id) => client.get(`/hospitals/${id}/state`).then((r) => r.data),

  createPatient: (body) => client.post('/patients', body).then((r) => r.data),
  getPatient: (id) => client.get(`/patients/${id}`).then((r) => r.data),
  createAssessment: (body) => client.post('/assessments', body).then((r) => r.data),

  getJourney: (id) => client.get(`/journeys/${id}`).then((r) => r.data),
  markEnRoute: (id) => client.post(`/journeys/${id}/mark-en-route`).then((r) => r.data),
  markArrived: (id) => client.post(`/journeys/${id}/mark-arrived`).then((r) => r.data),
  markUnderCare: (id) => client.post(`/journeys/${id}/mark-under-care`).then((r) => r.data),
  listHospitalJourneys: (hospitalId) => client.get(`/hospitals/${hospitalId}/journeys`).then((r) => r.data),

  createPatientRequest: (body) => client.post('/patient-requests', body).then((r) => r.data),
  getPatientRequest: (id) => client.get(`/patient-requests/${id}`).then((r) => r.data),
  listHospitalRequestResponses: (hospitalId) => client.get(`/hospitals/${hospitalId}/patient-request-responses`).then((r) => r.data),
  acceptResponse: (responseId) => client.post(`/patient-request-responses/${responseId}/accept`).then((r) => r.data),
  declineResponse: (responseId, reason) => client.post(`/patient-request-responses/${responseId}/decline`, { reason }).then((r) => r.data),
  selectHospital: (requestId, hospitalId) => client.post(`/patient-requests/${requestId}/select`, { hospital_id: hospitalId }).then((r) => r.data),
  confirmSelection: (responseId, stillEligible) => client.post(`/patient-request-responses/${responseId}/confirm`, { still_eligible: stillEligible }).then((r) => r.data),
  cancelRequest: (requestId) => client.post(`/patient-requests/${requestId}/cancel`).then((r) => r.data),

  emergencyDispatch: (body) => client.post('/emergency-dispatch', body).then((r) => r.data),

  parseReferralDocument: (body) => client.post('/referrals/parse-document', body).then((r) => r.data),
  listHospitalReferralResponses: (hospitalId) => client.get(`/hospitals/${hospitalId}/referral-responses`).then((r) => r.data),
  createReferral: (body) => client.post('/referrals', body).then((r) => r.data),
  getReferral: (id) => client.get(`/referrals/${id}`).then((r) => r.data),
  acceptReferral: (id, hospitalId) => client.post(`/referrals/${id}/accept`, { hospital_id: hospitalId }).then((r) => r.data),
  declineReferral: (id, hospitalId, reason) => client.post(`/referrals/${id}/decline`, { hospital_id: hospitalId, reason }).then((r) => r.data),

  startTransfer: (transferId) => client.post(`/transfers/${transferId}/start`).then((r) => r.data),
  markReceived: (transferId) => client.post(`/transfers/${transferId}/received`).then((r) => r.data),
  completeHandoff: (transferId, body) => client.post(`/handoffs/${transferId}/complete`, body).then((r) => r.data),

  simulatorSetHospitalState: (body, token) =>
    client
      .post('/simulator/hospital-state', body, { headers: { 'X-Demo-Admin-Token': token } })
      .then((r) => r.data),
  simulatorNetworkOverview: (token) =>
    client.get('/simulator/network-overview', { headers: { 'X-Demo-Admin-Token': token } }).then((r) => r.data),
}
