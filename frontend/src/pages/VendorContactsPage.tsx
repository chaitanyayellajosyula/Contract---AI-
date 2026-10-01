import { useEffect, useState } from 'react'
import { fetchVendorContacts } from '../lib/api'

type VendorContact = {
  id: number
  full_name: string
  email: string
  phone: string | null
  designation: string | null
  vendor_id: number
}

export default function VendorContactsPage() {
  const [contacts, setContacts] = useState<VendorContact[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    fetchVendorContacts()
      .then((result) => { if (active) setContacts(result as VendorContact[]) })
      .catch(() => { if (active) setContacts([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  return (
    <section className="space-y-4">
      <header className="border-b border-slate-800 pb-4">
        <p className="text-sm font-medium text-cyan-400">Relationships</p>
        <h1 className="mt-1 text-2xl font-semibold text-white">Vendor contacts</h1>
      </header>
      {loading ? <p className="text-sm text-slate-400">Loading contacts…</p> : contacts.length === 0 ? (
        <p className="border-y border-slate-800 py-4 text-sm text-slate-400">No vendor contacts found.</p>
      ) : (
        <div className="overflow-x-auto border-y border-slate-800">
          <table className="min-w-full text-left text-sm text-slate-300">
            <thead>
              <tr className="border-b border-slate-800 text-xs text-slate-500">
                <th className="px-3 py-3 font-medium">Name</th>
                <th className="px-3 py-3 font-medium">Email</th>
                <th className="px-3 py-3 font-medium">Phone</th>
                <th className="px-3 py-3 font-medium">Role</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((contact) => (
                <tr key={contact.id} className="border-b border-slate-800/70 last:border-0">
                  <td className="px-3 py-3 font-medium text-white">{contact.full_name}</td>
                  <td className="px-3 py-3"><a href={`mailto:${contact.email}`} className="text-cyan-300 hover:text-cyan-200">{contact.email}</a></td>
                  <td className="px-3 py-3">{contact.phone || 'Not recorded'}</td>
                  <td className="px-3 py-3">{contact.designation || 'Not recorded'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}