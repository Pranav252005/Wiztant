#!/usr/bin/env node
/**
 * Standalone diagnostic script for virtual-desktop follow.
 * Run this in a terminal to test which workspace tools work on your system.
 *
 * Usage: node scripts/diagnose_workspace.js
 */

const { exec, spawn } = require('child_process');

function run(cmd) {
  return new Promise((resolve) => {
    exec(cmd, (err, stdout, stderr) => {
      resolve({
        ok: !err,
        code: err ? err.code : 0,
        stdout: stdout?.trim() || '',
        stderr: stderr?.trim() || '',
      });
    });
  });
}

async function main() {
  console.log('=== Wiztant Workspace Diagnostic ===\n');
  console.log('Platform:', process.platform);
  console.log('PID:', process.pid);
  console.log('XDG_SESSION_TYPE:', process.env.XDG_SESSION_TYPE || '(not set)');
  console.log('');

  // 1. Check which tools are available
  console.log('--- Tool Availability ---');
  const tools = ['xprop', 'xdotool', 'wmctrl', 'gdbus'];
  for (const tool of tools) {
    const r = await run(`which ${tool}`);
    console.log(`${tool}: ${r.ok ? r.stdout : 'NOT FOUND'}`);
  }
  console.log('');

  // 2. Check X11 root properties
  console.log('--- X11 Root Properties ---');
  const xpropDesktop = await run('xprop -root _NET_CURRENT_DESKTOP');
  console.log('_NET_CURRENT_DESKTOP:', xpropDesktop.ok ? xpropDesktop.stdout : `FAIL (${xpropDesktop.stderr})`);

  const xpropTotal = await run('xprop -root _NET_NUMBER_OF_DESKTOPS');
  console.log('_NET_NUMBER_OF_DESKTOPS:', xpropTotal.ok ? xpropTotal.stdout : `FAIL (${xpropTotal.stderr})`);
  console.log('');

  // 3. Check xdotool desktop queries
  console.log('--- xdotool Desktop Queries ---');
  const xdoDesktop = await run('xdotool get_desktop');
  console.log('get_desktop:', xdoDesktop.ok ? xdoDesktop.stdout : `FAIL (${xdoDesktop.stderr})`);

  const xdoTotal = await run('xdotool get_num_desktops');
  console.log('get_num_desktops:', xdoTotal.ok ? xdoTotal.stdout : `FAIL (${xdoTotal.stderr})`);
  console.log('');

  // 4. Check window discovery
  console.log('--- Window Discovery ---');
  const xdoSearchPid = await run(`xdotool search --pid ${process.pid}`);
  console.log(`search --pid ${process.pid}:`, xdoSearchPid.ok ? xdoSearchPid.stdout || '(empty)' : `FAIL (${xdoSearchPid.stderr})`);

  const xdoSearchPill = await run(`xdotool search --name 'whiztant-pill'`);
  console.log("search --name 'whiztant-pill':", xdoSearchPill.ok ? xdoSearchPill.stdout || '(empty)' : `FAIL (${xdoSearchPill.stderr})`);

  const xdoSearchOverlay = await run(`xdotool search --name 'whiztant-overlay'`);
  console.log("search --name 'whiztant-overlay':", xdoSearchOverlay.ok ? xdoSearchOverlay.stdout || '(empty)' : `FAIL (${xdoSearchOverlay.stderr})`);

  const wmctrlList = await run('wmctrl -l');
  if (wmctrlList.ok) {
    const whizLines = wmctrlList.stdout.split('\n').filter((l) => l.toLowerCase().includes('whiztant'));
    console.log('wmctrl -l whiztant matches:', whizLines.length ? whizLines.join('\n') : '(none)');
  } else {
    console.log('wmctrl -l:', `FAIL (${wmctrlList.stderr})`);
  }
  console.log('');

  // 5. Test xprop -spy (start it, wait 2s, kill it)
  console.log('--- xprop -spy Test ---');
  let spyOutput = '';
  const spy = spawn('xprop', ['-spy', '-root', '_NET_CURRENT_DESKTOP']);
  spy.stdout.on('data', (d) => { spyOutput += d.toString(); });
  spy.stderr.on('data', (d) => { console.log('xprop stderr:', d.toString().trim()); });
  spy.on('error', (err) => { console.log('xprop spawn error:', err.message); });

  await new Promise((r) => setTimeout(r, 2000));
  spy.kill();
  console.log('xprop output after 2s:', spyOutput.trim() || '(none — try switching desktops while running)');
  console.log('');

  // 6. GNOME gdbus test
  console.log('--- GNOME gdbus Test ---');
  const gdbusTest = await run('gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "1+1"');
  console.log('GNOME Shell.Eval:', gdbusTest.ok ? gdbusTest.stdout : `FAIL (${gdbusTest.stderr})`);
  console.log('');

  console.log('=== End Diagnostic ===');
  console.log('');
  console.log('NOTES:');
  console.log('- If search --name returned empty, Electron is likely on native Wayland.');
  console.log('- The fix: Electron must run with --ozone-platform=x11 (XWayland).');
  console.log('- The app now forces this automatically on Linux.');
}

main().catch(console.error);
