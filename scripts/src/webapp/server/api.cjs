const fs = require("fs");
const path = require("path");
const { applicationDefault, cert, getApps, initializeApp } = require("firebase-admin/app");
const { FieldValue, getFirestore } = require("firebase-admin/firestore");

// Load webapp/.env into process.env so this module works whether it is required by the
// Vite dev server or any other host. We parse the file directly (not Vite's loadEnv,
// which lets an ambient process.env value shadow the file) so a stale
// GOOGLE_APPLICATION_CREDENTIALS pointing at a missing file can be overridden.
function loadDotenv() {
  const envPath = path.resolve(__dirname, "..", ".env");

  if (!fs.existsSync(envPath)) {
    return;
  }

  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    const eq = line.indexOf("=");

    if (!trimmed || trimmed.startsWith("#") || eq === -1) {
      continue;
    }

    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();

    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }

    const alreadySet = key in process.env;
    const staleCredPath =
      key === "GOOGLE_APPLICATION_CREDENTIALS" && alreadySet && !fs.existsSync(process.env[key]);

    if (key && (!alreadySet || staleCredPath)) {
      process.env[key] = value;
    }
  }
}

loadDotenv();

const projectId = process.env.FIREBASE_PROJECT_ID || "restaurant-robocup-2026";

let db;

// Credentials come from the environment only — never from a file committed to the repo.
//   FIREBASE_SERVICE_ACCOUNT        inline service-account JSON (preferred for deploys/CI)
//   GOOGLE_APPLICATION_CREDENTIALS  path to a local service-account JSON (standard Google ADC)
// See .env.example.
function getCredential() {
  const inlineServiceAccount = process.env.FIREBASE_SERVICE_ACCOUNT;

  if (inlineServiceAccount) {
    return cert(JSON.parse(inlineServiceAccount));
  }

  const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;

  // Fail fast and catchably here: if we hand applicationDefault() a missing path, the
  // file check happens later inside async gRPC and surfaces as an unhandled rejection
  // that crashes the whole dev server.
  if (credentialsPath && !fs.existsSync(credentialsPath)) {
    throw new Error(
      `GOOGLE_APPLICATION_CREDENTIALS points to a missing file: ${credentialsPath}. ` +
        "Set it to a valid service-account JSON (see .env.example) or unset it.",
    );
  }

  return applicationDefault();
}

function getDb() {
  if (!db) {
    if (getApps().length === 0) {
      initializeApp({
        credential: getCredential(),
        projectId,
      });
    }

    db = getFirestore();
  }

  return db;
}

function sendJson(res, statusCode, payload) {
  res.statusCode = statusCode;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(payload));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";

    req.on("data", (chunk) => {
      body += chunk;
    });

    req.on("end", () => {
      if (!body) {
        resolve({});
        return;
      }

      try {
        resolve(JSON.parse(body));
      } catch (error) {
        reject(error);
      }
    });
  });
}

async function listCollection(collectionName) {
  const snapshot = await getDb().collection(collectionName).get();

  return snapshot.docs.map((doc) => ({
    id: doc.id,
    ...doc.data(),
  }));
}

async function writeEvent({ type, severity = "info", message, entity_type, entity_id = null, created_by = "webapp", metadata = {} }) {
  const eventRef = await getDb().collection("events").add({
    type,
    severity,
    message,
    entity_type,
    entity_id,
    created_at: FieldValue.serverTimestamp(),
    created_by,
    metadata,
  });

  return eventRef.id;
}

function requireString(value, fieldName) {
  if (typeof value !== "string" || value.trim() === "") {
    const error = new Error(`${fieldName} is required`);
    error.statusCode = 400;
    throw error;
  }

  return value.trim();
}

function requireInteger(value, fieldName, min, max) {
  const number = Number(value);

  if (!Number.isInteger(number) || number < min || number > max) {
    const error = new Error(`${fieldName} must be an integer from ${min} to ${max}`);
    error.statusCode = 400;
    throw error;
  }

  return number;
}

function fail(message, statusCode = 400) {
  const error = new Error(message);
  error.statusCode = statusCode;
  throw error;
}

async function handleSnapshot(_req, res) {
  const [entrance, menu, orders, robots, tables, commands, tasks, events] = await Promise.all([
    listCollection("entrance"),
    listCollection("menu"),
    listCollection("orders"),
    listCollection("robots"),
    listCollection("tables"),
    listCollection("commands"),
    listCollection("tasks"),
    listCollection("events"),
  ]);

  sendJson(res, 200, {
    mode: "live",
    role: process.env.WEBAPP_DEFAULT_ROLE || "manager",
    entrance,
    menu,
    orders,
    robots,
    tables,
    commands,
    tasks,
    events,
  });
}

async function handleCreateParty(req, res) {
  const body = await readBody(req);
  const partySize = requireInteger(body.party_size, "party_size", 1, 12);
  const notes = typeof body.notes === "string" ? body.notes : "";

  const partyRef = await getDb().collection("entrance").add({
    party_size: partySize,
    status: "waiting",
    detected_by: "manual",
    assigned_table: null,
    arrived_at: FieldValue.serverTimestamp(),
    notes,
    created_by: "webapp",
    updated_at: FieldValue.serverTimestamp(),
  });

  await writeEvent({
    type: "party_created",
    message: `Manual party of ${partySize} added to entrance queue.`,
    entity_type: "party",
    entity_id: partyRef.id,
  });

  sendJson(res, 201, { id: partyRef.id });
}

async function handleAssignParty(req, res) {
  const body = await readBody(req);
  const partyId = requireString(body.party_id, "party_id");
  const tableId = requireString(body.table_id, "table_id");
  const [partyDoc, tableDoc] = await Promise.all([
    getDb().collection("entrance").doc(partyId).get(),
    getDb().collection("tables").doc(tableId).get(),
  ]);

  if (!partyDoc.exists) {
    fail("party not found", 404);
  }

  if (!tableDoc.exists) {
    fail("table not found", 404);
  }

  const table = tableDoc.data();

  if (["occupied", "needs_cleaning", "unavailable"].includes(table.status)) {
    fail(`table ${tableId} is not assignable while ${table.status}`);
  }

  const batch = getDb().batch();
  const partyRef = getDb().collection("entrance").doc(partyId);
  const tableRef = getDb().collection("tables").doc(tableId);

  batch.update(partyRef, {
    status: "assigned",
    assigned_table: tableId,
    assigned_at: FieldValue.serverTimestamp(),
    updated_at: FieldValue.serverTimestamp(),
  });
  batch.update(tableRef, {
    status: "assigned",
    current_party: partyId,
    last_updated: FieldValue.serverTimestamp(),
  });

  await batch.commit();
  await writeEvent({
    type: "party_assigned",
    message: `Party ${partyId} assigned to table ${tableId}.`,
    entity_type: "party",
    entity_id: partyId,
    metadata: { table_id: tableId },
  });

  sendJson(res, 200, { ok: true });
}

async function handleSeatParty(req, res) {
  const body = await readBody(req);
  const partyId = requireString(body.party_id, "party_id");
  const tableId = requireString(body.table_id, "table_id");
  const [partyDoc, tableDoc] = await Promise.all([
    getDb().collection("entrance").doc(partyId).get(),
    getDb().collection("tables").doc(tableId).get(),
  ]);

  if (!partyDoc.exists) {
    fail("party not found", 404);
  }

  if (!tableDoc.exists) {
    fail("table not found", 404);
  }

  const batch = getDb().batch();

  batch.update(getDb().collection("entrance").doc(partyId), {
    status: "seated",
    seated_at: FieldValue.serverTimestamp(),
    updated_at: FieldValue.serverTimestamp(),
  });
  batch.update(getDb().collection("tables").doc(tableId), {
    status: "occupied",
    current_party: partyId,
    occupied_since: FieldValue.serverTimestamp(),
    last_updated: FieldValue.serverTimestamp(),
  });

  await batch.commit();
  await writeEvent({
    type: "party_seated",
    message: `Party ${partyId} seated at table ${tableId}.`,
    entity_type: "table",
    entity_id: tableId,
    metadata: { party_id: partyId },
  });

  sendJson(res, 200, { ok: true });
}

async function handleUpdateTable(req, res) {
  const body = await readBody(req);
  const tableId = requireString(body.table_id, "table_id");
  const status = requireString(body.status, "status");
  const update = {
    status,
    last_updated: FieldValue.serverTimestamp(),
  };

  if (status === "empty") {
    update.current_order = null;
    update.current_party = null;
    update.occupied_since = null;
  }

  await getDb().collection("tables").doc(tableId).update(update);
  await writeEvent({
    type: "table_updated",
    message: `Table ${tableId} marked ${status.replace("_", " ")}.`,
    entity_type: "table",
    entity_id: tableId,
    metadata: { status },
  });

  sendJson(res, 200, { ok: true });
}

async function handleCreateOrder(req, res) {
  const body = await readBody(req);
  const tableId = requireString(body.table_id, "table_id");
  const items = Array.isArray(body.items) ? body.items : [];
  const tableDoc = await getDb().collection("tables").doc(tableId).get();

  if (!tableDoc.exists) {
    fail("table not found", 404);
  }

  if (tableDoc.data().status === "unavailable") {
    fail("cannot create order for an unavailable table");
  }

  if (items.length === 0) {
    fail("items must include at least one item");
  }

  const orderRef = await getDb().collection("orders").add({
    table_id: tableId,
    status: "draft",
    items,
    assigned_robot: null,
    used_tray: null,
    notes: typeof body.notes === "string" ? body.notes : "",
    created_at: FieldValue.serverTimestamp(),
    created_by: "webapp",
    updated_at: FieldValue.serverTimestamp(),
  });

  await getDb().collection("tables").doc(tableId).update({
    current_order: orderRef.id,
    last_updated: FieldValue.serverTimestamp(),
  });
  await writeEvent({
    type: "order_created",
    message: `Order ${orderRef.id} created for table ${tableId}.`,
    entity_type: "order",
    entity_id: orderRef.id,
    metadata: { table_id: tableId },
  });

  sendJson(res, 201, { id: orderRef.id });
}

const nextOrderStatus = {
  detected: "confirmed",
  draft: "confirmed",
  confirmed: "preparing",
  preparing: "ready",
  ready: "collecting",
  collecting: "delivering",
  delivering: "delivered",
};

async function handleAdvanceOrder(req, res) {
  const body = await readBody(req);
  const orderId = requireString(body.order_id, "order_id");
  const orderRef = getDb().collection("orders").doc(orderId);
  const orderDoc = await orderRef.get();

  if (!orderDoc.exists) {
    fail("order not found", 404);
  }

  const order = orderDoc.data();
  const status = body.status || nextOrderStatus[order.status];

  if (!status) {
    fail(`order status ${order.status} cannot be advanced`);
  }

  const update = {
    status,
    updated_at: FieldValue.serverTimestamp(),
  };

  if (status === "confirmed") update.confirmed_at = FieldValue.serverTimestamp();
  if (status === "ready") update.ready_at = FieldValue.serverTimestamp();
  if (status === "delivered") update.delivered_at = FieldValue.serverTimestamp();

  const batch = getDb().batch();
  batch.update(orderRef, update);

  if (["delivered", "cancelled", "failed"].includes(status) && typeof order.table_id === "string") {
    batch.update(getDb().collection("tables").doc(order.table_id), {
      current_order: null,
      last_updated: FieldValue.serverTimestamp(),
    });
  }

  await batch.commit();
  await writeEvent({
    type: "order_updated",
    message: `Order ${orderId} marked ${status}.`,
    entity_type: "order",
    entity_id: orderId,
    metadata: { status },
  });

  sendJson(res, 200, { ok: true, status });
}

async function handleCommand(req, res) {
  const body = await readBody(req);
  const commandType = requireString(body.command_type, "command_type");
  const robotId = typeof body.robot_id === "string" ? body.robot_id : null;
  const target = body.target && typeof body.target === "object" ? body.target : {};
  const params = body.params && typeof body.params === "object" ? body.params : {};
  const idempotencyKey = typeof body.idempotency_key === "string" ? body.idempotency_key : `${commandType}-${Date.now()}`;
  const requiresRobot = !["UPDATE_CUSTOMER_COUNT"].includes(commandType);

  if (requiresRobot && !robotId) {
    fail("robot_id is required for this command");
  }

  if (robotId) {
    const robotDoc = await getDb().collection("robots").doc(robotId).get();

    if (!robotDoc.exists) {
      fail("robot not found", 404);
    }

    if (robotDoc.data().status === "offline") {
      fail("offline robots cannot receive commands");
    }
  }

  if (["INTRODUCE_TABLE", "TAKE_ORDER", "DELIVER_ORDER"].includes(commandType) && typeof target.table_id !== "string") {
    fail("table_id is required for this command");
  }

  if (["COLLECT_ORDER", "DELIVER_ORDER"].includes(commandType) && typeof target.order_id !== "string") {
    fail("order_id is required for this command");
  }

  if (commandType === "EMERGENCY_STOP" && typeof params.reason !== "string") {
    fail("emergency stop requires a reason");
  }

  if (commandType === "GO_TO_LOCATION" && typeof target.waypoint !== "string") {
    fail("waypoint is required for this command");
  }

  if (commandType === "UPDATE_CUSTOMER_COUNT") {
    requireString(target.party_id, "party_id");
    requireInteger(params.party_size, "party_size", 1, 12);
  }

  const batch = getDb().batch();
  const commandRef = getDb().collection("commands").doc();
  const taskRef = getDb().collection("tasks").doc();

  batch.set(commandRef, {
    command_type: commandType,
    status: "queued",
    robot_id: robotId,
    target,
    params,
    idempotency_key: idempotencyKey,
    created_by: "webapp",
    created_at: FieldValue.serverTimestamp(),
    updated_at: FieldValue.serverTimestamp(),
    task_id: taskRef.id,
    ros_request_id: null,
    result: null,
  });
  batch.set(taskRef, {
    command_id: commandRef.id,
    task_type: commandType.toLowerCase(),
    status: "queued",
    robot_id: robotId,
    current_step: "Queued by web app; waiting for ROS bridge integration",
    progress_pct: 0,
    started_at: null,
    completed_at: null,
    error_msg: "",
    created_at: FieldValue.serverTimestamp(),
    updated_at: FieldValue.serverTimestamp(),
  });

  if (commandType === "COLLECT_ORDER" && typeof target.order_id === "string") {
    batch.update(getDb().collection("orders").doc(target.order_id), {
      status: "collecting",
      assigned_robot: robotId,
      updated_at: FieldValue.serverTimestamp(),
    });
  }

  if (commandType === "DELIVER_ORDER" && typeof target.order_id === "string") {
    batch.update(getDb().collection("orders").doc(target.order_id), {
      status: "delivering",
      assigned_robot: robotId,
      updated_at: FieldValue.serverTimestamp(),
    });
  }

  if (commandType === "UPDATE_CUSTOMER_COUNT" && typeof target.party_id === "string") {
    batch.update(getDb().collection("entrance").doc(target.party_id), {
      party_size: params.party_size,
      updated_at: FieldValue.serverTimestamp(),
    });
  }

  await batch.commit();
  await writeEvent({
    type: "command_queued",
    message: `${commandType} queued${robotId ? ` for ${robotId}` : ""}.`,
    entity_type: "command",
    entity_id: commandRef.id,
    metadata: { task_id: taskRef.id, target },
  });

  sendJson(res, 201, {
    command_id: commandRef.id,
    task_id: taskRef.id,
    status: "queued",
  });
}

async function route(req, res) {
  const url = new URL(req.url, "http://localhost");

  if (req.method === "GET" && url.pathname === "/api/health") {
    sendJson(res, 200, { ok: true, firestore: "admin", projectId });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/snapshot") {
    await handleSnapshot(req, res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/entrance") {
    await handleCreateParty(req, res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/entrance/assign-table") {
    await handleAssignParty(req, res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/entrance/seat") {
    await handleSeatParty(req, res);
    return;
  }

  if (req.method === "PATCH" && url.pathname === "/api/tables/status") {
    await handleUpdateTable(req, res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/orders") {
    await handleCreateOrder(req, res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/orders/advance") {
    await handleAdvanceOrder(req, res);
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/commands") {
    await handleCommand(req, res);
    return;
  }

  sendJson(res, 404, { error: "Not found" });
}

async function handleApi(req, res) {
  try {
    await route(req, res);
  } catch (error) {
    sendJson(res, error.statusCode || 500, {
      error: error.message || "Internal server error",
    });
  }
}

module.exports = { handleApi };
