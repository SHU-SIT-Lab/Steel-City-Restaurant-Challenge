const fs = require('fs');
const path = require('path');
const { applicationDefault, cert, initializeApp } = require('firebase-admin/app');
const { getFirestore } = require('firebase-admin/firestore');

// Initialize with your project ID.
// Use Application Default Credentials (ADC) or a service account JSON pointed to by
// the GOOGLE_APPLICATION_CREDENTIALS environment variable.
const fallbackServiceAccountPath = path.resolve(
    __dirname,
    '../../../docs/webapp/restaurant-robocup-2026-firebase-adminsdk-fbsvc-2b44375b91.json'
);

function getCredential() {
    const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;

    if (credentialsPath && fs.existsSync(credentialsPath)) {
        return applicationDefault();
    }

    if (fs.existsSync(fallbackServiceAccountPath)) {
        if (credentialsPath) {
            console.error(`Ignoring missing GOOGLE_APPLICATION_CREDENTIALS file: ${credentialsPath}`);
            console.error(`Using fallback service account file: ${fallbackServiceAccountPath}`);
        }

        return cert(require(fallbackServiceAccountPath));
    }

    return applicationDefault();
}

initializeApp({
    credential: getCredential(),
    projectId: 'restaurant-robocup-2026'
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
