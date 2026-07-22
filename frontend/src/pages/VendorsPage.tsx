import { useEffect, useState } from 'react'
import { fetchVendorContacts } from '../lib/api'

export default function VendorsPage() {
  const [contacts, setContacts] = useState<any[]>([])

  useEffect(() => {
    async function loadContacts() {
      try {
        const data = await fetchVendorContacts()
        setContacts(data || [])
      } catch {
        setContacts([])
      }
    }

    void loadContacts()
  }, [])

  return (
    <div className="space-y-4 rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
      <h1 className="text-2xl font-semibold text-white">Vendor Contacts</h1>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-slate-300">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-400">
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Phone</th>
              <th className="px-3 py-2">LinkedIn</th>
              <th className="px-3 py-2">Designation</th>
            </tr>
          </thead>
          <tbody>
            {contacts.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-slate-400">No vendor contacts found.</td>
              </tr>
            ) : (
              contacts.map((contact) => (
                <tr key={contact.id} className="border-b border-slate-800/70">
                  <td className="px-3 py-2 text-white">{contact.full_name || '—'}</td>
                  <td className="px-3 py-2">{contact.email || '—'}</td>
                  <td className="px-3 py-2">{contact.phone || '—'}</td>
                  <td className="px-3 py-2">{contact.linkedin_url || '—'}</td>
                  <td className="px-3 py-2">{contact.designation || '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
