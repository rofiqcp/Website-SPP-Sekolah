// RFID scanner hook: HID keyboard mode + optional Web Serial
import { useState, useCallback, useEffect, useRef } from 'react';

export function useRfidScanner(context = 'default') {
  const [state, setState] = useState({ mode: null, lastUid: null, ts: 0, status: 'disconnected', capabilities: { hid: true, serial: false } });
  const buffer = useRef('');
  const lastScanRef = useRef(0);
  const debounce = useRef(null);
  const serialPort = useRef(null);
  const serialReader = useRef(null);
  const abortSerial = useRef(false);

  const handleUid = useCallback((uid) => {
    const now = Date.now();
    if (now - lastScanRef.current < 2000) return;
    lastScanRef.current = now;
    setState(p => ({ ...p, lastUid: uid, ts: now }));
  }, []);

  useEffect(() => {
    const caps = { hid: true, serial: 'serial' in navigator };
    setState(p => ({ ...p, capabilities: caps }));

    const input = document.createElement('input');
    input.setAttribute('data-rfid', context);
    input.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0;pointer-events:none';
    document.body.appendChild(input);
    input.focus();

    const onKey = (e) => {
      if (e.target === input || !e.target) {
        if (e.key === 'Enter') {
          clearTimeout(debounce.current);
          const raw = buffer.current.trim();
          buffer.current = '';
          if (raw.length >= 4) handleUid(raw);
        } else if (e.key.length === 1) {
          buffer.current += e.key;
          clearTimeout(debounce.current);
          debounce.current = setTimeout(() => { buffer.current = ''; }, 500);
        }
      }
    };
    const refocus = () => { if (document.activeElement !== input && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') input.focus(); };

    document.addEventListener('keydown', onKey);
    window.addEventListener('focus', refocus);
    input.addEventListener('blur', refocus);
    setState(p => ({ ...p, mode: 'hid', status: 'ready' }));

    return () => {
      input.remove();
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('focus', refocus);
      abortSerial.current = true;
      if (serialReader.current) {
        serialReader.current.cancel().then(() => serialReader.current = null);
      }
      if (serialPort.current) {
        serialPort.current.close().then(() => serialPort.current = null);
      }
    };
  }, [context, handleUid]);

  const connectSerial = useCallback(async () => {
    if (!('serial' in navigator)) {
      setState(p => ({ ...p, status: 'Serial tidak didukung' }));
      return null;
    }
    try {
      let port;
      const ports = await navigator.serial.getPorts();
      if (ports.length > 0) {
        port = ports[0];
      } else {
        port = await navigator.serial.requestPort();
      }
      await port.open({ baudRate: 9600, dataBits: 8, stopBits: 1, parity: 'none', flowControl: 'none' });
      serialPort.current = port;
      const textDecoder = new TextDecoderStream();
      port.readable.pipeTo(textDecoder.writable);
      const reader = textDecoder.readable.getReader();
      serialReader.current = reader;
      abortSerial.current = false;
      setState(p => ({ ...p, mode: 'serial', status: 'serial_connected', serialPort: port }));

      (async () => {
        try {
          while (!abortSerial.current) {
            const { value, done } = await reader.read();
            if (done) break;
            const lines = value.split(/[\r\n]+/);
            for (const line of lines) {
              const uid = line.trim();
              if (uid.length >= 4) handleUid(uid);
            }
          }
        } catch { setState(p => ({ ...p, status: 'serial_disconnected' })); }
      })();
      return port;
    } catch (e) {
      setState(p => ({ ...p, status: `Serial gagal: ${e.message}` }));
      return null;
    }
  }, [handleUid]);

  return { state, connectSerial };
}
