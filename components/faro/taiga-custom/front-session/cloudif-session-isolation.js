(function () {
  "use strict";
  var keys = { token: true, refresh: true, userInfo: true };
  var proto = window.Storage && window.Storage.prototype;
  if (!proto || !window.localStorage || !window.sessionStorage) return;

  var originalGet = proto.getItem;
  var originalSet = proto.setItem;
  var originalRemove = proto.removeItem;
  var originalClear = proto.clear;
  var local = window.localStorage;
  var session = window.sessionStorage;

  Object.keys(keys).forEach(function (key) {
    // Never migrate an old persistent login into the new browser session.
    originalRemove.call(local, key);
  });

  proto.getItem = function (key) {
    key = String(key);
    if (this === local && keys[key]) return originalGet.call(session, key);
    return originalGet.call(this, key);
  };
  proto.setItem = function (key, value) {
    key = String(key);
    if (this === local && keys[key]) return originalSet.call(session, key, value);
    return originalSet.call(this, key, value);
  };
  proto.removeItem = function (key) {
    key = String(key);
    if (this === local && keys[key]) return originalRemove.call(session, key);
    return originalRemove.call(this, key);
  };
  proto.clear = function () {
    if (this === local) {
      Object.keys(keys).forEach(function (key) { originalRemove.call(session, key); });
    }
    return originalClear.call(this);
  };
})();
