(function () {
  "use strict";
  var keys = { token: true, refresh: true, userInfo: true };
  var generationKey = "cloudif-auth-generation";
  var channelName = "cloudif-taiga-auth";
  var proto = window.Storage && window.Storage.prototype;
  if (!proto || !window.localStorage || !window.sessionStorage) return;

  var originalGet = proto.getItem;
  var originalSet = proto.setItem;
  var originalRemove = proto.removeItem;
  var originalClear = proto.clear;
  var local = window.localStorage;
  var session = window.sessionStorage;
  var channel = null;

  function clearSessionAuth() {
    Object.keys(keys).forEach(function (key) { originalRemove.call(session, key); });
    originalRemove.call(session, generationKey);
  }

  function replacedByAnotherLogin(nextGeneration) {
    var current = originalGet.call(session, generationKey);
    if (!current || !nextGeneration || current === nextGeneration) return;
    clearSessionAuth();
    window.location.replace("/login?reason=session-replaced");
  }

  function newGeneration() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return String(Date.now()) + "-" + Math.random().toString(36).slice(2);
  }

  function announceAuthenticatedSession() {
    var current = originalGet.call(session, generationKey);
    if (current) return;
    current = newGeneration();
    originalSet.call(session, generationKey, current);
    originalSet.call(local, generationKey, current);
    if (channel) channel.postMessage({ generation: current });
  }

  Object.keys(keys).forEach(function (key) {
    // Never migrate an old persistent login into the new browser session.
    originalRemove.call(local, key);
  });

  if (typeof window.BroadcastChannel === "function") {
    channel = new BroadcastChannel(channelName);
    channel.onmessage = function (event) {
      replacedByAnotherLogin(event && event.data && event.data.generation);
    };
  }
  window.addEventListener("storage", function (event) {
    if (event.storageArea === local && event.key === generationKey) {
      replacedByAnotherLogin(event.newValue);
    }
  });

  proto.getItem = function (key) {
    key = String(key);
    if (this === local && keys[key]) return originalGet.call(session, key);
    return originalGet.call(this, key);
  };
  proto.setItem = function (key, value) {
    key = String(key);
    if (this === local && keys[key]) {
      var result = originalSet.call(session, key, value);
      if (key === "userInfo") announceAuthenticatedSession();
      return result;
    }
    return originalSet.call(this, key, value);
  };
  proto.removeItem = function (key) {
    key = String(key);
    if (this === local && keys[key]) return originalRemove.call(session, key);
    return originalRemove.call(this, key);
  };
  proto.clear = function () {
    if (this === local) clearSessionAuth();
    return originalClear.call(this);
  };
})();
