export function FileQueryUrl(
    apiUrl: string,
    instrument?: string,
    experimentNumber?: string,
    userNumber?: string,) {
    if (instrument != null && experimentNumber != null) {
        return `${apiUrl}/find_file/instrument/${instrument}/experiment_number/${experimentNumber}`
    }
    if (userNumber != null) {
        return `${apiUrl}/find_file/generic/user_number/${userNumber}`
    }
    if (experimentNumber != null) {
        return `${apiUrl}/find_file/generic/experiment_number/${experimentNumber}`
    }
    return null
}