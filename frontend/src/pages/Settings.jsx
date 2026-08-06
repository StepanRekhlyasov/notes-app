import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { clearToken } from '../auth.js';
import { useLang } from '../i18n.jsx';

const STATUS_POLL_MS = 2000;

export default function Settings() {
  const { t } = useLang();
  const navigate = useNavigate();

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [pwError, setPwError] = useState(null);
  const [pwOk, setPwOk] = useState(false);

  const [deletePw, setDeletePw] = useState('');
  const [deleteError, setDeleteError] = useState(null);

  const [tgLoading, setTgLoading] = useState(true);
  const [tgConnected, setTgConnected] = useState(false);
  const [tgUrl, setTgUrl] = useState(null);
  const [tgError, setTgError] = useState(null);
  const [tgBusy, setTgBusy] = useState(false);
  const [tgAwaiting, setTgAwaiting] = useState(false);

  const pollTimerRef = useRef(null);

  const stopStatusPoll = () => {
    if (pollTimerRef.current != null) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const applyStatus = (status) => {
    setTgConnected(status.connected);
    setTgUrl(status.url || null);
    setTgError(null);
  };

  useEffect(() => {
    let alive = true;
    setTgLoading(true);
    api.getNotifications()
      .then((status) => {
        if (!alive) return;
        applyStatus(status);
      })
      .catch((err) => {
        if (alive) setTgError(err.message);
      })
      .finally(() => {
        if (alive) setTgLoading(false);
      });
    return () => {
      alive = false;
      stopStatusPoll();
    };
  }, []);

  useEffect(() => {
    if (!tgAwaiting) {
      stopStatusPoll();
      return undefined;
    }

    let cancelled = false;

    const tick = async () => {
      try {
        const status = await api.getNotifications();
        if (cancelled) return;
        if (status.connected) {
          applyStatus(status);
          setTgAwaiting(false);
          return;
        }
        setTgUrl(status.url || null);
      } catch (err) {
        if (!cancelled) setTgError(err.message);
      }
      if (!cancelled) {
        pollTimerRef.current = setTimeout(tick, STATUS_POLL_MS);
      }
    };

    tick();

    return () => {
      cancelled = true;
      stopStatusPoll();
    };
  }, [tgAwaiting]);

  const connectTelegram = () => {
    if (!tgUrl) return;
    setTgError(null);
    window.open(tgUrl, '_blank', 'noopener,noreferrer');
    setTgAwaiting(true);
  };

  const disconnectTelegram = async () => {
    setTgBusy(true);
    setTgError(null);
    setTgAwaiting(false);
    try {
      await api.disconnectNotifications();
      const status = await api.getNotifications();
      applyStatus(status);
    } catch (err) {
      setTgError(err.message);
    } finally {
      setTgBusy(false);
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    setPwError(null);
    setPwOk(false);
    try {
      await api.changePassword(currentPw, newPw);
      setPwOk(true);
      setCurrentPw('');
      setNewPw('');
    } catch (err) {
      setPwError(err.message);
    }
  };

  const deleteAccount = async (e) => {
    e.preventDefault();
    setDeleteError(null);
    if (!window.confirm(t('settings.confirmDelete'))) return;
    try {
      await api.deleteAccount(deletePw);
      clearToken();
      navigate('/login', { replace: true });
    } catch (err) {
      setDeleteError(err.message);
    }
  };

  const showTgLoader = tgLoading || tgAwaiting;

  return (
    <div className="settings-page">
      <h1>{t('settings.title')}</h1>

      <section className="settings-card">
        <h2>{t('settings.changePasswordTitle')}</h2>
        <form onSubmit={changePassword}>
          <label>
            {t('settings.currentPassword')}
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            {t('settings.newPassword')}
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              minLength={6}
              autoComplete="new-password"
            />
          </label>
          {pwError && <div className="error">{pwError}</div>}
          {pwOk && <div className="success">{t('settings.passwordChanged')}</div>}
          <button type="submit" className="btn btn-primary">{t('settings.submit')}</button>
        </form>
      </section>

      <section className="settings-card danger">
        <h2>{t('settings.dangerZone')}</h2>
        <h3>{t('settings.deleteAccountTitle')}</h3>
        <p className="settings-hint">{t('settings.deleteAccountHint')}</p>
        <form onSubmit={deleteAccount}>
          <label>
            {t('settings.confirmPassword')}
            <input
              type="password"
              value={deletePw}
              onChange={(e) => setDeletePw(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {deleteError && <div className="error">{deleteError}</div>}
          <button type="submit" className="btn btn-danger">{t('settings.deleteAccount')}</button>
        </form>
      </section>

      <section className="settings-card">
        <h2>{t('settings.telegramConnectTitle')}</h2>
        <p className="settings-hint">{t('settings.telegramConnectHint')}</p>
        {tgError && <div className="error">{tgError}</div>}
        {showTgLoader ? (
          <div className="settings-loader" role="status" aria-live="polite">
            <span className="settings-spinner" aria-hidden="true" />
            {tgAwaiting ? t('settings.telegramWaiting') : t('settings.telegramLoading')}
          </div>
        ) : tgConnected ? (
          <button
            type="button"
            className="btn btn-danger"
            onClick={disconnectTelegram}
            disabled={tgBusy}
          >
            {t('settings.telegramDisconnect')}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={connectTelegram}
            disabled={!tgUrl}
          >
            {t('settings.telegramConnect')}
          </button>
        )}
      </section>
    </div>
  );
}
