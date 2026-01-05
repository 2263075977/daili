// 京东 Cookie 获取脚本
const $ = new Env('京东Cookie获取');

!(async () => {
    if ($request.method === 'OPTIONS') {
        return;
    }

    const cookie = $request.headers['Cookie'] || $request.headers['cookie'];
    
    if (cookie && cookie.includes('pt_key=')) {
        $.log('成功获取京东 Cookie');
        
        const ptKey = cookie.match(/pt_key=([^;]+)/)?.[1];
        const ptPin = cookie.match(/pt_pin=([^;]+)/)?.[1];
        
        if (ptKey && ptPin) {
            $.log(`pt_pin: ${ptPin}`);
            $.log(`pt_key: ${ptKey.substring(0, 10)}...`);
            
            $.setdata(cookie, 'jd_cookie');
            $.msg('京东Cookie', `用户: ${ptPin}`, 'Cookie已更新');
        }
    } else {
        $.log('未检测到有效的京东 Cookie');
    }
})()
    .catch((e) => $.logErr(e))
    .finally(() => $.done());

function Env(t, e) {
    class s {
        constructor(t) { this.env = t; }
        send(t, e = 'GET') {
            t = 'string' == typeof t ? { url: t } : t;
            let s = this.get;
            return 'POST' === e && (s = this.post), new Promise((e, i) => {
                s.call(this, t, (t, s, o) => { t ? i(t) : e(s); });
            });
        }
        get(t) { return this.send.call(this.env, t); }
        post(t) { return this.send.call(this.env, t, 'POST'); }
    }
    return new class {
        constructor(t, e) {
            this.name = t, this.http = new s(this), this.platform = 'Surge';
        }
        log(...t) { console.log(t.join(' ')); }
        logErr(t, e) { this.log('', `❗️错误!`, t.message); }
        msg(t = '', e = '', i = '') {
            $notification.post(t, e, i);
        }
        getdata(t) { return $persistentStore.read(t); }
        setdata(t, e) { return $persistentStore.write(t, e); }
        done(t = {}) { this.done(); }
    }(t, e);
}
