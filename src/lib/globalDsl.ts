let dslCode = ``;

export function setDslCode(code: string) {
    console.log("Setting DSL code:", code);
    dslCode = code;
}

export function getDslCode() {
    return dslCode;
}