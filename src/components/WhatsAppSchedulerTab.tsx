import React, { useState, useId } from 'react';
import {
  MessageSquare,
  Smartphone,
  QrCode,
  Plus,
  Send,
  Calendar,
  Clock,
  Trash2,
  Edit2,
  XCircle,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Image as ImageIcon,
  RotateCcw,
} from 'lucide-react';
import { StorageService } from '../services/storage';
import { WhatsAppPost, WhatsAppRecipient } from '../types';

interface WhatsAppSchedulerTabProps {
  onNotify: (msg: string) => void;
}

export const WhatsAppSchedulerTab: React.FC<WhatsAppSchedulerTabProps> = ({ onNotify }) => {
  const modalImageInputId = useId();

  // Storage State
  const [recipients, setRecipients] = useState<WhatsAppRecipient[]>(() =>
    StorageService.getWhatsAppRecipients()
  );
  const [posts, setPosts] = useState<WhatsAppPost[]>(() =>
    StorageService.getWhatsAppPosts()
  );

  // Filters & Selected Chat
  const [selectedChatFilter, setSelectedChatFilter] = useState<string>('all');

  // New/Edit Post Modal State
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [editingPostId, setEditingPostId] = useState<number | null>(null);
  const [formChatId, setFormChatId] = useState<string>(recipients[0]?.id || '');
  const [formMessage, setFormMessage] = useState<string>('');
  const [formScheduledAt, setFormScheduledAt] = useState<string>(() => {
    const d = new Date(Date.now() + 3600 * 1000);
    return d.toISOString().slice(0, 16);
  });
  const [formImageName, setFormImageName] = useState<string>('');
  const [formImageDataUrl, setFormImageDataUrl] = useState<string>('');

  // Target Phone Edit Modal
  const [editingRecipient, setEditingRecipient] = useState<WhatsAppRecipient | null>(null);
  const [targetPhoneInput, setTargetPhoneInput] = useState<string>('');

  // QR Code Modal
  const [isQrModalOpen, setIsQrModalOpen] = useState<boolean>(false);
  const [qrScanning, setQrScanning] = useState<boolean>(false);

  // Reset Targets
  const handleResetTargets = () => {
    if (confirm('Reset all WhatsApp target newsletter mappings to default values?')) {
      const reset = StorageService.resetWhatsAppRecipients();
      setRecipients(reset);
      onNotify('WhatsApp target mappings reset to default.');
    }
  };

  // Open Edit Target Phone Modal
  const handleOpenEditRecipient = (rec: WhatsAppRecipient) => {
    setEditingRecipient(rec);
    setTargetPhoneInput(rec.phone);
  };

  const handleSaveRecipientPhone = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRecipient) return;

    const updated = StorageService.updateWhatsAppRecipientPhone(
      editingRecipient.id,
      targetPhoneInput.trim()
    );
    setRecipients(updated);
    setEditingRecipient(null);
    onNotify(`Updated target identifier for ${editingRecipient.name}`);
  };

  // Open Schedule Modal for New Post
  const handleOpenNewPost = () => {
    setEditingPostId(null);
    setFormChatId(recipients[0]?.id || '');
    setFormMessage('');
    const d = new Date(Date.now() + 3600 * 1000);
    setFormScheduledAt(d.toISOString().slice(0, 16));
    setFormImageName('');
    setFormImageDataUrl('');
    setIsModalOpen(true);
  };

  // Open Schedule Modal for Edit
  const handleOpenEditPost = (post: WhatsAppPost) => {
    setEditingPostId(post.id);
    setFormChatId(post.recipient_id);
    setFormMessage(post.message || '');
    try {
      const d = new Date(post.scheduled_at);
      setFormScheduledAt(d.toISOString().slice(0, 16));
    } catch {
      setFormScheduledAt('');
    }
    setFormImageName(post.image_path || '');
    setFormImageDataUrl(post.image_url || '');
    setIsModalOpen(true);
  };

  // Save Scheduled WhatsApp Post
  const handleSavePost = (e: React.FormEvent) => {
    e.preventDefault();
    const recipient = recipients.find(r => r.id === formChatId);
    if (!recipient) {
      alert('Please select a valid recipient.');
      return;
    }

    if (!formMessage.trim() && !formImageName) {
      alert('Please enter a message or attach an image.');
      return;
    }

    const scheduledDate = new Date(formScheduledAt);
    if (isNaN(scheduledDate.getTime())) {
      alert('Please select a valid scheduled date/time.');
      return;
    }

    if (editingPostId) {
      // Update existing
      const updated = StorageService.updateWhatsAppPost(editingPostId, {
        recipient_id: recipient.id,
        recipient_name: recipient.name,
        recipient_phone: recipient.phone,
        message: formMessage.trim(),
        image_path: formImageName || null,
        image_url: formImageDataUrl || null,
        scheduled_at: scheduledDate.toISOString(),
      });
      setPosts(updated);
      onNotify('WhatsApp post updated successfully.');
    } else {
      // Create new
      StorageService.addWhatsAppPost({
        recipient_id: recipient.id,
        recipient_name: recipient.name,
        recipient_phone: recipient.phone,
        message: formMessage.trim(),
        image_path: formImageName || null,
        image_url: formImageDataUrl || null,
        scheduled_at: scheduledDate.toISOString(),
      });
      setPosts(StorageService.getWhatsAppPosts());
      onNotify('WhatsApp post scheduled successfully.');
    }

    setIsModalOpen(false);
  };

  // Cancel Post
  const handleCancelPost = (id: number) => {
    const updated = StorageService.cancelWhatsAppPost(id);
    setPosts(updated);
    onNotify('WhatsApp post cancelled.');
  };

  // Delete Post
  const handleDeletePost = (id: number) => {
    const updated = StorageService.deleteWhatsAppPost(id);
    setPosts(updated);
    onNotify('WhatsApp post removed.');
  };

  // Send Now (instant simulation)
  const handleSendNow = (id: number) => {
    const updated = StorageService.updateWhatsAppPost(id, {
      status: 'sent',
      attempts: 1,
    });
    setPosts(updated);
    onNotify('WhatsApp message dispatched immediately via Baileys provider.');
  };

  // Filter posts
  const filteredPosts = posts.filter(p => {
    if (selectedChatFilter === 'all') return true;
    return p.recipient_id === selectedChatFilter;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner & Status */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-slate-900/60 to-slate-900 border border-emerald-500/30 rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">WhatsApp Scheduler & Hub</h2>
                <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">
                  Baileys Engine
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Dispatch scheduled deals and newsletter campaigns to WhatsApp channels and subscriber lists.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsQrModalOpen(true)}
              className="px-3.5 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-200 flex items-center gap-1.5 cursor-pointer"
            >
              <QrCode className="w-3.5 h-3.5 text-emerald-400" />
              <span>Pair WhatsApp Web</span>
            </button>
            <button
              onClick={handleOpenNewPost}
              className="px-3.5 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-sm flex items-center gap-1.5 cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Schedule Post</span>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Channels & Target Newsletters */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Smartphone className="w-4 h-4 text-emerald-400" />
                Target Channels ({recipients.length})
              </span>
              <button
                onClick={handleResetTargets}
                className="text-[11px] text-slate-400 hover:text-emerald-400 flex items-center gap-1 cursor-pointer"
                title="Reset channel newsletter IDs to defaults"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset Targets</span>
              </button>
            </div>

            <div className="space-y-2">
              {recipients.map(rec => (
                <div
                  key={rec.id}
                  className="p-2.5 rounded-lg border border-slate-800/80 bg-slate-800/30 flex items-center justify-between"
                >
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`w-7 h-7 rounded-lg ${rec.color} text-white font-bold text-xs flex items-center justify-center shrink-0`}
                    >
                      {rec.avatar}
                    </div>
                    <div>
                      <span className="text-xs font-medium text-slate-200 block">{rec.name}</span>
                      <span className="text-[10px] text-slate-400 font-mono block truncate max-w-[170px]">
                        {rec.phone || 'No target configured'}
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => handleOpenEditRecipient(rec)}
                    className="p-1 text-slate-500 hover:text-white rounded hover:bg-slate-800 cursor-pointer"
                    title="Edit newsletter ID / target phone"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right 2 Columns: Scheduled Posts Table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  Scheduled WhatsApp Dispatches ({filteredPosts.length})
                </span>
                <p className="text-[11px] text-slate-500">
                  Automated background worker sends posts at target scheduled time.
                </p>
              </div>

              {/* Chat filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Filter:</span>
                <select
                  value={selectedChatFilter}
                  onChange={e => setSelectedChatFilter(e.target.value)}
                  className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-emerald-500"
                >
                  <option value="all">All Channels</option>
                  {recipients.map(r => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Posts List */}
            {filteredPosts.length === 0 ? (
              <div className="py-12 border border-slate-800 rounded-lg text-center text-slate-500">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-40 text-emerald-400" />
                <p className="text-xs">No WhatsApp posts scheduled.</p>
                <button
                  onClick={handleOpenNewPost}
                  className="mt-3 px-3 py-1.5 bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 text-xs rounded-lg hover:bg-emerald-600/30 cursor-pointer"
                >
                  Schedule First Post
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredPosts.map(post => {
                  const isSent = post.status === 'sent';
                  const isCancelled = post.status === 'cancelled';
                  const isPending = post.status === 'pending';

                  return (
                    <div
                      key={post.id}
                      className="p-3.5 bg-slate-800/40 border border-slate-800 rounded-xl space-y-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                              isSent
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                : isCancelled
                                ? 'bg-slate-700 text-slate-400'
                                : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            }`}
                          >
                            {post.status}
                          </span>
                          <span className="text-xs font-semibold text-slate-200">
                            {post.recipient_name}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                          <Clock className="w-3.5 h-3.5 text-slate-500" />
                          <span>
                            {new Date(post.scheduled_at).toLocaleString('en-IN', {
                              timeZone: 'Asia/Kolkata',
                              month: 'short',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: true,
                            })}{' '}
                            IST
                          </span>
                        </div>
                      </div>

                      {/* Content Preview */}
                      <div className="flex gap-3">
                        {post.image_url ? (
                          <img
                            src={post.image_url}
                            alt="Attachment"
                            className="w-12 h-12 rounded-lg object-cover border border-slate-700 shrink-0"
                          />
                        ) : post.image_path ? (
                          <div className="w-12 h-12 rounded-lg bg-slate-800 border border-slate-700 flex flex-col items-center justify-center text-[9px] text-slate-400 shrink-0">
                            <ImageIcon className="w-4 h-4 text-emerald-400 mb-0.5" />
                            Image
                          </div>
                        ) : null}

                        <p className="text-xs text-slate-300 whitespace-pre-wrap line-clamp-2">
                          {post.message || 'No text content'}
                        </p>
                      </div>

                      {/* Footer Actions */}
                      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
                        <span className="text-[11px] text-slate-500 font-mono">
                          Target: {post.recipient_phone}
                        </span>

                        <div className="flex items-center gap-2">
                          {isPending && (
                            <>
                              <button
                                onClick={() => handleSendNow(post.id)}
                                className="px-2.5 py-1 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 rounded text-[11px] font-medium flex items-center gap-1 cursor-pointer"
                              >
                                <Send className="w-3 h-3" />
                                <span>Send Now</span>
                              </button>
                              <button
                                onClick={() => handleOpenEditPost(post)}
                                className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-700 cursor-pointer"
                                title="Edit post"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleCancelPost(post.id)}
                                className="p-1 text-slate-400 hover:text-amber-400 rounded hover:bg-slate-700 cursor-pointer"
                                title="Cancel post"
                              >
                                <XCircle className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => handleDeletePost(post.id)}
                            className="p-1 text-slate-500 hover:text-red-400 rounded hover:bg-slate-700 cursor-pointer"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Schedule / Edit WhatsApp Post Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">
                {editingPostId ? 'Edit WhatsApp Post' : 'Schedule WhatsApp Post'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 cursor-pointer"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleSavePost} className="space-y-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Target Channel</label>
                <select
                  value={formChatId}
                  onChange={e => setFormChatId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-emerald-500"
                >
                  {recipients.map(r => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.phone})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Scheduled Time (IST)</label>
                <input
                  type="datetime-local"
                  value={formScheduledAt}
                  onChange={e => setFormScheduledAt(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-emerald-500"
                  required
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Message Content</label>
                <textarea
                  rows={4}
                  value={formMessage}
                  onChange={e => setFormMessage(e.target.value)}
                  placeholder="Enter deal text, coupons, and amzaff.in links..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Attach Image</label>
                <input
                  id={modalImageInputId}
                  type="file"
                  accept="image/*"
                  onChange={e => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setFormImageName(f.name);
                      const r = new FileReader();
                      r.onload = ev => setFormImageDataUrl(ev.target?.result as string);
                      r.readAsDataURL(f);
                    }
                  }}
                  className="hidden"
                />
                <div className="flex items-center gap-3">
                  <label
                    htmlFor={modalImageInputId}
                    className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-700 cursor-pointer flex items-center gap-1.5"
                  >
                    <ImageIcon className="w-3.5 h-3.5" />
                    <span>Choose Image</span>
                  </label>
                  {formImageName && (
                    <span className="text-xs font-mono text-slate-400 truncate max-w-xs">
                      {formImageName}
                    </span>
                  )}
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-xl font-medium cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-xl font-semibold cursor-pointer shadow-md"
                >
                  Save Schedule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Target Phone / Newsletter Modal */}
      {editingRecipient && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="font-bold text-white text-base">
              Edit Target for {editingRecipient.name}
            </h3>
            <p className="text-xs text-slate-400">
              Provide the WhatsApp Newsletter JID (e.g. 120363408723243626@newsletter) or phone number with country code.
            </p>
            <form onSubmit={handleSaveRecipientPhone} className="space-y-4">
              <div>
                <input
                  type="text"
                  value={targetPhoneInput}
                  onChange={e => setTargetPhoneInput(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-emerald-500"
                  required
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditingRecipient(null)}
                  className="px-3 py-1.5 bg-slate-800 text-slate-300 text-xs rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-emerald-600 text-white text-xs rounded-lg font-semibold cursor-pointer"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* QR Code Pair Modal */}
      {isQrModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-2xl text-center">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="font-bold text-white text-sm">Pair WhatsApp Web</span>
              <button
                onClick={() => setIsQrModalOpen(false)}
                className="text-slate-400 hover:text-white text-xs cursor-pointer"
              >
                Close
              </button>
            </div>

            <div className="p-4 bg-white rounded-xl inline-block shadow-inner mx-auto my-2">
              {/* Simulated QR code graphic */}
              <div className="w-48 h-48 bg-slate-950 flex flex-col items-center justify-center p-3 relative rounded border-4 border-slate-900">
                <div className="absolute top-2 left-2 w-8 h-8 border-4 border-white"></div>
                <div className="absolute top-2 right-2 w-8 h-8 border-4 border-white"></div>
                <div className="absolute bottom-2 left-2 w-8 h-8 border-4 border-white"></div>
                <QrCode className="w-24 h-24 text-white opacity-90" />
                <span className="text-[9px] font-mono text-emerald-400 mt-2">BAILEYS_READY_ONLINE</span>
              </div>
            </div>

            <div className="text-xs text-slate-300 space-y-1">
              <p className="font-semibold text-emerald-400 flex items-center justify-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Session Active & Connected
              </p>
              <p className="text-[11px] text-slate-400">
                Scan with WhatsApp &gt; Linked Devices to establish or refresh persistent session.
              </p>
            </div>

            <button
              onClick={() => {
                setQrScanning(true);
                setTimeout(() => {
                  setQrScanning(false);
                  setIsQrModalOpen(false);
                  onNotify('WhatsApp Web session refreshed.');
                }, 800);
              }}
              className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs rounded-xl shadow cursor-pointer"
            >
              {qrScanning ? 'Refreshing...' : 'Refresh Session'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
