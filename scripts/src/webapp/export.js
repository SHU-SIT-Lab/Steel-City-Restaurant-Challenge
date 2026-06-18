const fs = require('fs');
const path = require('path');
const { applicationDefault, cert, initializeApp } = require('firebase-admin/app');
const { getFirestore } = require('firebase-admin/firestore');

// Load .env (if present) so a standalone `node export.js` picks up the same
// credentials as the dev server. Only fills vars that aren't already set.
function loadDotenv() {
    const envPath = path.resolve(__dirname, '.env');

    if (!fs.existsSync(envPath)) {
        return;
    }

    for (const line of fs.readFileSync(envPath, 'utf8').split('\n')) {
        const trimmed = line.trim();
        const eq = line.indexOf('=');

        if (!trimmed || trimmed.startsWith('#') || eq === -1) {
            continue;
        }

        const key = line.slice(0, eq).trim();
        let value = line.slice(eq + 1).trim();

        if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
            value = value.slice(1, -1);
        }

        if (!key) {
            continue;
        }

        // Prefer an existing env var, EXCEPT when GOOGLE_APPLICATION_CREDENTIALS is
        // already set to a path that doesn't exist (a stale/placeholder default) —
        // then let .env win so local dev isn't blocked by an ambient value.
        const alreadySet = key in process.env;
        const staleCredPath =
            key === 'GOOGLE_APPLICATION_CREDENTIALS' && alreadySet && !fs.existsSync(process.env[key]);

        if (!alreadySet || staleCredPath) {
            process.env[key] = value;
        }
    }
}

loadDotenv();

// Credentials come from the environment only — never from a file committed to the repo.
//   FIREBASE_SERVICE_ACCOUNT        inline service-account JSON (preferred for deploys/CI)
//   GOOGLE_APPLICATION_CREDENTIALS  path to a local service-account JSON (standard Google ADC)
function getCredential() {
    const inlineServiceAccount = process.env.FIREBASE_SERVICE_ACCOUNT;

    if (inlineServiceAccount) {
        return cert(JSON.parse(inlineServiceAccount));
    }

    const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;

    if (credentialsPath && !fs.existsSync(credentialsPath)) {
        throw new Error(
            `GOOGLE_APPLICATION_CREDENTIALS points to a missing file: ${credentialsPath}. ` +
                'Set it to a valid service-account JSON (see .env.example) or unset it.'
        );
    }

    return applicationDefault();
}

initializeApp({
    credential: getCredential(),
    projectId: process.env.FIREBASE_PROJECT_ID || 'restaurant-robocup-2026'
});

// Use the modular getFirestore() API which is the recommended approach
// for recent versions of firebase-admin.
const db = getFirestore();

async function traverseFirestore(collectionRef, indent = '') {
    const snapshot = await collectionRef.get();

    for (const doc of snapshot.docs) {
        console.log(`\n${indent}collection: ${collectionRef.id}`);
        console.log(`${indent}  doc: ${doc.id}`);

        const data = doc.data();
        for (const [key, value] of Object.entries(data)) {
            // Formats arrays/objects cleanly, similar to your output example
            const formattedValue = Array.isArray(value)
                ? `[${value.join(', ')}]`
                : typeof value === 'object' && value !== null
                    ? JSON.stringify(value)
                    : value;

            console.log(`${indent}    ${key}: ${formattedValue}`);
        }

        // Recursively handle any nested subcollections
        const subcollections = await doc.ref.listCollections();
        for (const subcol of subcollections) {
            await traverseFirestore(subcol, indent + '  ');
        }
    }
}

async function run() {
    try {
        const rootCollections = await db.listCollections();
        for (const col of rootCollections) {
            await traverseFirestore(col);
        }
    } catch (error) {
        console.error("Error exporting Firestore data:", error);
        process.exitCode = 1;
    }
}

run();
